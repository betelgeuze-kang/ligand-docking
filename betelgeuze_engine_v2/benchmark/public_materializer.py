"""Result-free materialization for the frozen public redocking contract cohort.

The materializer accepts caller-supplied bytes, verifies every byte against the
frozen upstream artifact identities, splits bounded multi-record SDF input,
selects exactly one reference record by exact labeled-graph isomorphism, and
emits bounded heavy-atom symmetry mappings.  It performs no network access,
docking, scoring, RMSD evaluation, benchmark execution, or claim promotion.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.docking.metrics import MAX_SYMMETRY_PERMUTATIONS
from betelgeuze_engine_v2.io import parse_sdf_v2000
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    canonical_topology_sha256,
)

from .public_protocol import (
    FROZEN_PUBLIC_BENCHMARK_PROTOCOL_SHA256,
    FrozenPublicBenchmarkProtocol,
    PublicBenchmarkCaseDefinition,
    frozen_public_benchmark_protocol,
)


PUBLIC_BENCHMARK_MATERIALIZER_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_materializer/1.0.0"
)
PUBLIC_BENCHMARK_CASE_MATERIALIZATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_case_materialization/1.0.0"
)
PUBLIC_BENCHMARK_MATERIALIZATION_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_benchmark_materialization_manifest/1.0.0"
)
PUBLIC_BENCHMARK_MATERIALIZER_ID = (
    "posebusters_packaged_public_redocking_input_materializer/1.0.0"
)
PUBLIC_BENCHMARK_MAX_SDF_BYTES = 16 * 1024 * 1024
PUBLIC_BENCHMARK_MAX_SDF_RECORDS = 256
PUBLIC_BENCHMARK_MAX_GRAPH_ATOMS = 512
PUBLIC_BENCHMARK_MAX_GRAPH_BONDS = 2_048
PUBLIC_BENCHMARK_MAX_GRAPH_SEARCH_STATES = 2_000_000


class PublicBenchmarkMaterializerError(ValueError):
    """External benchmark bytes cannot be materialized without ambiguity."""


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
        raise PublicBenchmarkMaterializerError(
            "public benchmark materialization is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PublicBenchmarkMaterializerError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _require_bytes(value: object, *, name: str, maximum: int) -> bytes:
    if not isinstance(value, bytes):
        raise TypeError(f"{name} must be bytes")
    if not value or len(value) > maximum:
        raise PublicBenchmarkMaterializerError(
            f"{name} is empty or exceeds its byte bound"
        )
    return value


def split_sdf_v2000_records(
    source: bytes,
    *,
    max_records: int = PUBLIC_BENCHMARK_MAX_SDF_RECORDS,
    max_bytes: int = PUBLIC_BENCHMARK_MAX_SDF_BYTES,
) -> tuple[bytes, ...]:
    """Split exact ASCII SDF records while preserving each record's bytes."""

    payload = _require_bytes(source, name="SDF source", maximum=max_bytes)
    if type(max_records) is not int or max_records < 1:
        raise PublicBenchmarkMaterializerError(
            "max_records must be a positive integer"
        )
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PublicBenchmarkMaterializerError(
            "SDF source must be ASCII"
        ) from exc
    if "\r" in text or not text.endswith("\n"):
        raise PublicBenchmarkMaterializerError(
            "SDF source must use LF line endings and end with a newline"
        )

    records: list[bytes] = []
    current: list[str] = []
    for line in text.splitlines(keepends=True):
        current.append(line)
        if line == "$$$$\n":
            if len(current) <= 1:
                raise PublicBenchmarkMaterializerError(
                    "SDF source contains an empty record"
                )
            records.append("".join(current).encode("ascii"))
            current = []
            if len(records) > max_records:
                raise PublicBenchmarkMaterializerError(
                    "SDF source exceeds the record bound"
                )
    if current:
        raise PublicBenchmarkMaterializerError(
            "SDF source contains an unterminated record"
        )
    if not records:
        raise PublicBenchmarkMaterializerError(
            "SDF source contains no records"
        )
    if b"".join(records) != payload:
        raise PublicBenchmarkMaterializerError(
            "SDF record splitting did not preserve the source bytes"
        )
    return tuple(records)


def _atom_label(atom: Any) -> tuple[object, ...]:
    return (
        str(atom.element).upper(),
        int(atom.formal_charge),
        None if atom.isotope_mass_number is None else int(atom.isotope_mass_number),
        bool(atom.is_aromatic),
        None if atom.chirality is None else str(atom.chirality),
    )


def _bond_label(bond: Any) -> tuple[object, ...]:
    order = float(bond.order)
    if not math.isfinite(order):
        raise PublicBenchmarkMaterializerError(
            "molecular graph contains a non-finite bond order"
        )
    return (
        order.hex(),
        bool(bond.is_aromatic),
        None if bond.stereo is None else str(bond.stereo),
    )


@dataclass(frozen=True, slots=True)
class _LabeledGraph:
    atom_labels: tuple[tuple[object, ...], ...]
    adjacency: tuple[tuple[tuple[int, tuple[object, ...]], ...], ...]
    edge_count: int
    heavy_atom_indices: tuple[int, ...]
    invariant_sha256: str

    @property
    def atom_count(self) -> int:
        return len(self.atom_labels)

    @property
    def degree_signatures(self) -> tuple[tuple[object, ...], ...]:
        rows: list[tuple[object, ...]] = []
        for index, neighbors in enumerate(self.adjacency):
            incident = tuple(
                sorted(
                    (
                        bond_label,
                        self.atom_labels[neighbor],
                    )
                    for neighbor, bond_label in neighbors
                )
            )
            rows.append((self.atom_labels[index], len(neighbors), incident))
        return tuple(rows)


def _labeled_graph(system: AllAtomSystem) -> _LabeledGraph:
    atom_count = int(system.atom_count)
    if atom_count < 1 or atom_count > PUBLIC_BENCHMARK_MAX_GRAPH_ATOMS:
        raise PublicBenchmarkMaterializerError(
            "molecular graph atom count is outside the materializer bound"
        )
    if len(system.bonds) > PUBLIC_BENCHMARK_MAX_GRAPH_BONDS:
        raise PublicBenchmarkMaterializerError(
            "molecular graph bond count exceeds the materializer bound"
        )
    atom_labels = tuple(_atom_label(atom) for atom in system.atoms)
    adjacency_rows: list[list[tuple[int, tuple[object, ...]]]] = [
        [] for _ in range(atom_count)
    ]
    seen_edges: set[tuple[int, int]] = set()
    edge_projection: list[tuple[object, ...]] = []
    for bond in system.bonds:
        first, second = sorted((int(bond.atom_i), int(bond.atom_j)))
        if first < 0 or second >= atom_count or first == second:
            raise PublicBenchmarkMaterializerError(
                "molecular graph contains an invalid bond index"
            )
        pair = (first, second)
        if pair in seen_edges:
            raise PublicBenchmarkMaterializerError(
                "molecular graph contains duplicate bonds"
            )
        seen_edges.add(pair)
        label = _bond_label(bond)
        adjacency_rows[first].append((second, label))
        adjacency_rows[second].append((first, label))
        edge_projection.append(
            (
                atom_labels[first],
                atom_labels[second],
                label,
            )
        )
    adjacency = tuple(
        tuple(sorted(row, key=lambda item: (item[0], item[1])))
        for row in adjacency_rows
    )
    heavy = tuple(
        index
        for index, label in enumerate(atom_labels)
        if label[0] != "H"
    )
    if not heavy:
        raise PublicBenchmarkMaterializerError(
            "molecular graph contains no heavy atoms"
        )
    invariant = {
        "schema_id": "betelgeuze.engine_v2_public_labeled_graph_invariant/1.0.0",
        "atom_count": atom_count,
        "edge_count": len(seen_edges),
        "atom_label_counts": [
            {"label": list(label), "count": count}
            for label, count in sorted(Counter(atom_labels).items())
        ],
        "degree_signature_counts": [
            {"signature": repr(signature), "count": count}
            for signature, count in sorted(
                Counter(
                    (
                        atom_labels[index],
                        len(adjacency[index]),
                        tuple(
                            sorted(
                                (
                                    bond_label,
                                    atom_labels[neighbor],
                                )
                                for neighbor, bond_label in adjacency[index]
                            )
                        ),
                    )
                    for index in range(atom_count)
                ).items(),
                key=lambda item: repr(item[0]),
            )
        ],
        "edge_label_counts": [
            {"edge": repr(row), "count": count}
            for row, count in sorted(
                Counter(edge_projection).items(),
                key=lambda item: repr(item[0]),
            )
        ],
        "heavy_atom_count": len(heavy),
    }
    return _LabeledGraph(
        atom_labels=atom_labels,
        adjacency=adjacency,
        edge_count=len(seen_edges),
        heavy_atom_indices=heavy,
        invariant_sha256=_sha256(invariant),
    )


def _edge_map(graph: _LabeledGraph) -> dict[tuple[int, int], tuple[object, ...]]:
    result: dict[tuple[int, int], tuple[object, ...]] = {}
    for first, neighbors in enumerate(graph.adjacency):
        for second, label in neighbors:
            if first < second:
                result[(first, second)] = label
    return result


def exact_graph_isomorphisms(
    source: AllAtomSystem,
    target: AllAtomSystem,
    *,
    max_mappings: int = MAX_SYMMETRY_PERMUTATIONS,
    max_search_states: int = PUBLIC_BENCHMARK_MAX_GRAPH_SEARCH_STATES,
) -> tuple[tuple[int, ...], ...]:
    """Return every bounded source-to-target atom mapping for exact graph labels."""

    if type(max_mappings) is not int or max_mappings < 1:
        raise PublicBenchmarkMaterializerError(
            "max_mappings must be a positive integer"
        )
    if type(max_search_states) is not int or max_search_states < 1:
        raise PublicBenchmarkMaterializerError(
            "max_search_states must be a positive integer"
        )
    source_graph = _labeled_graph(source)
    target_graph = _labeled_graph(target)
    if (
        source_graph.atom_count != target_graph.atom_count
        or source_graph.edge_count != target_graph.edge_count
        or Counter(source_graph.atom_labels) != Counter(target_graph.atom_labels)
        or Counter(source_graph.degree_signatures)
        != Counter(target_graph.degree_signatures)
    ):
        return ()

    source_edges = _edge_map(source_graph)
    target_edges = _edge_map(target_graph)
    candidates: dict[int, tuple[int, ...]] = {}
    for source_index, signature in enumerate(source_graph.degree_signatures):
        rows = tuple(
            target_index
            for target_index, target_signature in enumerate(
                target_graph.degree_signatures
            )
            if target_signature == signature
        )
        if not rows:
            return ()
        candidates[source_index] = rows
    order = tuple(
        sorted(
            range(source_graph.atom_count),
            key=lambda index: (
                len(candidates[index]),
                -len(source_graph.adjacency[index]),
                repr(source_graph.atom_labels[index]),
                index,
            ),
        )
    )
    mapping: dict[int, int] = {}
    used_targets: set[int] = set()
    results: list[tuple[int, ...]] = []
    states = 0

    def edge_label(
        edges: Mapping[tuple[int, int], tuple[object, ...]],
        first: int,
        second: int,
    ) -> tuple[object, ...] | None:
        return edges.get(tuple(sorted((first, second))))

    def visit(depth: int) -> None:
        nonlocal states
        states += 1
        if states > max_search_states:
            raise PublicBenchmarkMaterializerError(
                "exact graph matching exceeded the search-state bound"
            )
        if depth == len(order):
            result = tuple(mapping[index] for index in range(source_graph.atom_count))
            results.append(result)
            if len(results) > max_mappings:
                raise PublicBenchmarkMaterializerError(
                    "exact graph symmetry exceeds the mapping bound"
                )
            return
        source_index = order[depth]
        for target_index in candidates[source_index]:
            if target_index in used_targets:
                continue
            compatible = True
            for other_source, other_target in mapping.items():
                if edge_label(source_edges, source_index, other_source) != edge_label(
                    target_edges,
                    target_index,
                    other_target,
                ):
                    compatible = False
                    break
            if not compatible:
                continue
            mapping[source_index] = target_index
            used_targets.add(target_index)
            visit(depth + 1)
            used_targets.remove(target_index)
            del mapping[source_index]

    visit(0)
    return tuple(sorted(set(results)))


def _heavy_atom_bijections(
    source: AllAtomSystem,
    target: AllAtomSystem,
    mappings: Sequence[Sequence[int]],
) -> tuple[tuple[int, ...], ...]:
    source_graph = _labeled_graph(source)
    target_graph = _labeled_graph(target)
    target_heavy_position = {
        atom_index: position
        for position, atom_index in enumerate(target_graph.heavy_atom_indices)
    }
    rows: list[tuple[int, ...]] = []
    for mapping in mappings:
        if len(mapping) != source_graph.atom_count:
            raise PublicBenchmarkMaterializerError(
                "graph mapping atom count is inconsistent"
            )
        projected: list[int] = []
        for source_index in source_graph.heavy_atom_indices:
            target_index = int(mapping[source_index])
            if target_index not in target_heavy_position:
                raise PublicBenchmarkMaterializerError(
                    "graph mapping does not preserve heavy-atom identity"
                )
            projected.append(target_heavy_position[target_index])
        row = tuple(projected)
        if sorted(row) != list(range(len(target_graph.heavy_atom_indices))):
            raise PublicBenchmarkMaterializerError(
                "heavy-atom graph mapping is not a bijection"
            )
        rows.append(row)
    unique = tuple(sorted(set(rows)))
    if not unique:
        raise PublicBenchmarkMaterializerError(
            "exact graph matching produced no heavy-atom bijection"
        )
    if len(unique) > MAX_SYMMETRY_PERMUTATIONS:
        raise PublicBenchmarkMaterializerError(
            "heavy-atom symmetry exceeds the mapping bound"
        )
    return unique


@dataclass(frozen=True, slots=True)
class PublicBenchmarkCaseMaterialization:
    case_id: str
    case_input_sha256: str
    source_commit_sha: str
    receptor_sha256: str
    reference_ligands_sha256: str
    ligand_identity_seed_sha256: str
    selected_reference_record_index: int
    selected_reference_record_sha256: str
    selected_reference_system_sha256: str
    selected_reference_topology_sha256: str
    selected_reference_coordinates_sha256: str
    ligand_graph_invariant_sha256: str
    heavy_atom_count: int
    symmetry_permutations: tuple[tuple[int, ...], ...]
    materialization_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": PUBLIC_BENCHMARK_CASE_MATERIALIZATION_SCHEMA_ID,
            "case_id": self.case_id,
            "case_input_sha256": self.case_input_sha256,
            "source_commit_sha": self.source_commit_sha,
            "receptor_sha256": self.receptor_sha256,
            "reference_ligands_sha256": self.reference_ligands_sha256,
            "ligand_identity_seed_sha256": self.ligand_identity_seed_sha256,
            "selected_reference_record_index": self.selected_reference_record_index,
            "selected_reference_record_sha256": self.selected_reference_record_sha256,
            "selected_reference_system_sha256": self.selected_reference_system_sha256,
            "selected_reference_topology_sha256": self.selected_reference_topology_sha256,
            "selected_reference_coordinates_sha256": self.selected_reference_coordinates_sha256,
            "ligand_graph_invariant_sha256": self.ligand_graph_invariant_sha256,
            "heavy_atom_count": self.heavy_atom_count,
            "symmetry_permutation_count": len(self.symmetry_permutations),
            "symmetry_permutations": [
                list(row) for row in self.symmetry_permutations
            ],
            "ligand_identity_seed_coordinates_used": False,
            "receptor_coordinates_interpreted": False,
            "docking_executed": False,
            "metric_values_collected": False,
            "scientifically_validated": False,
            "claim_safe": False,
            "materialization_sha256": self.materialization_sha256,
        }


@dataclass(frozen=True, slots=True)
class PublicBenchmarkMaterializationRow:
    ordinal: int
    case_id: str
    case_input_sha256: str
    status: str
    materialization: PublicBenchmarkCaseMaterialization | None
    error_code: str = ""
    error_message: str = ""
    private_error_sha256: str = ""
    private_error_byte_length: int = 0

    @property
    def succeeded(self) -> bool:
        return self.status == "success" and self.materialization is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "case_id": self.case_id,
            "case_input_sha256": self.case_input_sha256,
            "status": self.status,
            "succeeded": self.succeeded,
            "materialization": (
                None if self.materialization is None else self.materialization.to_dict()
            ),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "private_error_sha256": self.private_error_sha256,
            "private_error_byte_length": self.private_error_byte_length,
        }


@dataclass(frozen=True, slots=True)
class PublicBenchmarkMaterializationManifest:
    protocol_sha256: str
    rows: tuple[PublicBenchmarkMaterializationRow, ...]
    manifest_sha256: str

    @property
    def success_count(self) -> int:
        return sum(row.succeeded for row in self.rows)

    @property
    def failure_count(self) -> int:
        return len(self.rows) - self.success_count

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": PUBLIC_BENCHMARK_MATERIALIZATION_MANIFEST_SCHEMA_ID,
            "materializer_id": PUBLIC_BENCHMARK_MATERIALIZER_ID,
            "protocol_sha256": self.protocol_sha256,
            "case_count": len(self.rows),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "all_cases_observed": True,
            "failure_rows_retained": True,
            "network_fetch_performed": False,
            "raw_artifact_bytes_embedded": False,
            "benchmark_execution_performed": False,
            "docking_results_collected": False,
            "metric_values_collected": False,
            "result_document_created": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
            "rows": [row.to_dict() for row in self.rows],
            "manifest_sha256": self.manifest_sha256,
        }


def materialize_public_benchmark_case(
    case: PublicBenchmarkCaseDefinition,
    *,
    receptor_bytes: bytes,
    reference_ligands_bytes: bytes,
    ligand_identity_seed_bytes: bytes,
) -> PublicBenchmarkCaseMaterialization:
    """Verify and materialize one result-free public redocking case."""

    if not isinstance(case, PublicBenchmarkCaseDefinition):
        raise TypeError("case must be PublicBenchmarkCaseDefinition")
    receptor_digest = case.receptor.verify_bytes(
        _require_bytes(
            receptor_bytes,
            name="receptor bytes",
            maximum=max(case.receptor.size_bytes, 1),
        )
    )
    reference_digest = case.reference_ligands.verify_bytes(
        _require_bytes(
            reference_ligands_bytes,
            name="reference ligand bytes",
            maximum=PUBLIC_BENCHMARK_MAX_SDF_BYTES,
        )
    )
    seed_digest = case.ligand_identity_seed.verify_bytes(
        _require_bytes(
            ligand_identity_seed_bytes,
            name="ligand identity seed bytes",
            maximum=PUBLIC_BENCHMARK_MAX_SDF_BYTES,
        )
    )
    seed_records = split_sdf_v2000_records(ligand_identity_seed_bytes)
    if len(seed_records) != 1:
        raise PublicBenchmarkMaterializerError(
            "ligand identity seed must contain exactly one SDF record"
        )
    seed_system = parse_sdf_v2000(
        seed_records[0].decode("ascii"),
        source_id=f"{case.case_id}:ligand-identity-seed",
    )
    seed_graph = _labeled_graph(seed_system)
    reference_records = split_sdf_v2000_records(reference_ligands_bytes)
    matches: list[tuple[int, bytes, AllAtomSystem, tuple[tuple[int, ...], ...]]] = []
    for index, record in enumerate(reference_records):
        reference_system = parse_sdf_v2000(
            record.decode("ascii"),
            source_id=f"{case.case_id}:reference:{index}",
        )
        mappings = exact_graph_isomorphisms(seed_system, reference_system)
        if mappings:
            matches.append((index, record, reference_system, mappings))
    if len(matches) != 1:
        raise PublicBenchmarkMaterializerError(
            "exactly one reference record must match the ligand seed graph"
        )
    selected_index, selected_record, selected_system, mappings = matches[0]
    heavy_mappings = _heavy_atom_bijections(
        seed_system,
        selected_system,
        mappings,
    )
    projection = {
        "schema_id": PUBLIC_BENCHMARK_CASE_MATERIALIZATION_SCHEMA_ID,
        "case_id": case.case_id,
        "case_input_sha256": case.input_sha256,
        "source_commit_sha": case.receptor.immutable_url.split("/")[-4],
        "receptor_sha256": receptor_digest,
        "reference_ligands_sha256": reference_digest,
        "ligand_identity_seed_sha256": seed_digest,
        "selected_reference_record_index": selected_index,
        "selected_reference_record_sha256": hashlib.sha256(selected_record).hexdigest(),
        "selected_reference_system_sha256": canonical_system_sha256(selected_system),
        "selected_reference_topology_sha256": canonical_topology_sha256(selected_system),
        "selected_reference_coordinates_sha256": canonical_coordinates_sha256(
            selected_system
        ),
        "ligand_graph_invariant_sha256": seed_graph.invariant_sha256,
        "heavy_atom_count": len(seed_graph.heavy_atom_indices),
        "symmetry_permutations": [list(row) for row in heavy_mappings],
        "ligand_identity_seed_coordinates_used": False,
        "receptor_coordinates_interpreted": False,
        "docking_executed": False,
        "metric_values_collected": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return PublicBenchmarkCaseMaterialization(
        case_id=case.case_id,
        case_input_sha256=case.input_sha256,
        source_commit_sha=str(projection["source_commit_sha"]),
        receptor_sha256=receptor_digest,
        reference_ligands_sha256=reference_digest,
        ligand_identity_seed_sha256=seed_digest,
        selected_reference_record_index=selected_index,
        selected_reference_record_sha256=str(
            projection["selected_reference_record_sha256"]
        ),
        selected_reference_system_sha256=str(
            projection["selected_reference_system_sha256"]
        ),
        selected_reference_topology_sha256=str(
            projection["selected_reference_topology_sha256"]
        ),
        selected_reference_coordinates_sha256=str(
            projection["selected_reference_coordinates_sha256"]
        ),
        ligand_graph_invariant_sha256=seed_graph.invariant_sha256,
        heavy_atom_count=len(seed_graph.heavy_atom_indices),
        symmetry_permutations=heavy_mappings,
        materialization_sha256=_sha256(projection),
    )


def materialize_frozen_public_benchmark_inputs(
    artifact_bytes_by_case: Mapping[str, Mapping[str, bytes]],
    *,
    protocol: FrozenPublicBenchmarkProtocol | None = None,
) -> PublicBenchmarkMaterializationManifest:
    """Materialize every protocol case while retaining every failure row."""

    active = protocol or frozen_public_benchmark_protocol()
    if not isinstance(active, FrozenPublicBenchmarkProtocol):
        raise TypeError("protocol must be FrozenPublicBenchmarkProtocol")
    if active.protocol_sha256 != FROZEN_PUBLIC_BENCHMARK_PROTOCOL_SHA256:
        raise PublicBenchmarkMaterializerError(
            "public benchmark protocol does not match the frozen identity"
        )
    if not isinstance(artifact_bytes_by_case, Mapping):
        raise TypeError("artifact_bytes_by_case must be a mapping")
    unexpected = set(artifact_bytes_by_case) - {
        case.case_id for case in active.cases
    }
    if unexpected:
        raise PublicBenchmarkMaterializerError(
            "artifact input contains cases outside the frozen protocol"
        )
    rows: list[PublicBenchmarkMaterializationRow] = []
    for ordinal, case in enumerate(active.cases):
        try:
            supplied = artifact_bytes_by_case.get(case.case_id)
            if not isinstance(supplied, Mapping) or set(supplied) != {
                "receptor",
                "reference_ligands",
                "ligand_identity_seed",
            }:
                raise PublicBenchmarkMaterializerError(
                    "case artifact input is missing or has unexpected roles"
                )
            materialization = materialize_public_benchmark_case(
                case,
                receptor_bytes=supplied["receptor"],
                reference_ligands_bytes=supplied["reference_ligands"],
                ligand_identity_seed_bytes=supplied["ligand_identity_seed"],
            )
            rows.append(
                PublicBenchmarkMaterializationRow(
                    ordinal=ordinal,
                    case_id=case.case_id,
                    case_input_sha256=case.input_sha256,
                    status="success",
                    materialization=materialization,
                )
            )
        except Exception as exc:
            receipt = failure_receipt(
                exc,
                public_message="public benchmark case materialization failed",
            )
            rows.append(
                PublicBenchmarkMaterializationRow(
                    ordinal=ordinal,
                    case_id=case.case_id,
                    case_input_sha256=case.input_sha256,
                    status="failure",
                    materialization=None,
                    error_code=receipt.public_error_code,
                    error_message=receipt.public_message,
                    private_error_sha256=receipt.private_error_sha256,
                    private_error_byte_length=receipt.private_error_byte_length,
                )
            )
    projection = {
        "schema_id": PUBLIC_BENCHMARK_MATERIALIZATION_MANIFEST_SCHEMA_ID,
        "materializer_id": PUBLIC_BENCHMARK_MATERIALIZER_ID,
        "protocol_sha256": active.protocol_sha256,
        "case_count": len(rows),
        "failure_rows_retained": True,
        "network_fetch_performed": False,
        "raw_artifact_bytes_embedded": False,
        "benchmark_execution_performed": False,
        "docking_results_collected": False,
        "metric_values_collected": False,
        "result_document_created": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "rows": [row.to_dict() for row in rows],
    }
    return PublicBenchmarkMaterializationManifest(
        protocol_sha256=active.protocol_sha256,
        rows=tuple(rows),
        manifest_sha256=_sha256(projection),
    )


__all__ = [
    "PUBLIC_BENCHMARK_CASE_MATERIALIZATION_SCHEMA_ID",
    "PUBLIC_BENCHMARK_MATERIALIZATION_MANIFEST_SCHEMA_ID",
    "PUBLIC_BENCHMARK_MATERIALIZER_ID",
    "PUBLIC_BENCHMARK_MATERIALIZER_SCHEMA_ID",
    "PUBLIC_BENCHMARK_MAX_GRAPH_ATOMS",
    "PUBLIC_BENCHMARK_MAX_GRAPH_BONDS",
    "PUBLIC_BENCHMARK_MAX_GRAPH_SEARCH_STATES",
    "PUBLIC_BENCHMARK_MAX_SDF_BYTES",
    "PUBLIC_BENCHMARK_MAX_SDF_RECORDS",
    "PublicBenchmarkCaseMaterialization",
    "PublicBenchmarkMaterializationManifest",
    "PublicBenchmarkMaterializationRow",
    "PublicBenchmarkMaterializerError",
    "exact_graph_isomorphisms",
    "materialize_frozen_public_benchmark_inputs",
    "materialize_public_benchmark_case",
    "split_sdf_v2000_records",
]
