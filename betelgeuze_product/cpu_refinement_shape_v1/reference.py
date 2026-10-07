"""Standalone, opt-in all-pair parent-shape contract; no molecular evaluator.

Coordinates are Angstrom, energy kcal/mol, and forces kcal/mol/Angstrom.
SHA-256 binds identity, not source authenticity: loaders require a separately
trusted expected digest. The adapter must admit *all* original ligand atoms,
including hydrogens, and supply the original canonical molecular identifier.
This module cannot infer omitted atoms, chemistry, source provenance, or chirality.

A zero-strength result is a sentinel for an adapter to return its original base
observation unchanged. It must not add zero tensors or dispatch the base twice.
The zero branch does not access trial coordinates; the base evaluator remains
responsible for their validation. Identity and reference integrity still apply.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from typing import Any, NamedTuple

SCHEMA = "parent_shape_reference/1.0.0"
CONTRACT_SCHEMA = "parent_shape_contract/1.0.0"
MIN_DISTANCE = 1e-8
MAX_ATOMS = 256
STRENGTHS = (0.0, 100.0, 1000.0)
PAIR_POLICY = "all_unique_unordered_atoms_in_one_connected_ligand_including_hydrogens"
NORMALIZATION = "1/M; M=N*(N-1)/2"
PARENT_ROLE = "original_supplied_parent"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
# The symbols identify atoms without introducing atomic/mass weighting.
_ELEMENTS = frozenset(("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn "
    "Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb "
    "Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir "
    "Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No "
    "Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og").split())


class ShapeContractError(ValueError):
    """Invalid identity, serialization, reference, or strength."""


class ShapeDomainError(ShapeContractError):
    """Coordinates or arithmetic are outside the declared binary64 domain."""


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ShapeContractError(f"{name} must be a nonempty, unpadded string")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ShapeContractError(f"{name} must not contain control characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ShapeContractError(f"{name} is not valid Unicode") from exc
    return value


def _sha(value: Any, name: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise ShapeContractError(f"{name} must be lowercase SHA-256 hex")
    return value


def _finite(value: float, name: str) -> float:
    if not math.isfinite(value):
        raise ShapeDomainError(f"nonfinite {name}")
    return value


def _number(value: Any, name: str) -> float:
    if type(value) not in (int, float):
        raise ShapeDomainError(f"{name} must be a binary64 number, not a boolean")
    try:
        return _finite(float(value), name)
    except OverflowError as exc:
        raise ShapeDomainError(f"overflow in {name}") from exc


def _sequence(value: Any, name: str) -> tuple:
    # Restrict to concrete containers: no generators with mutable or unbounded
    # iteration semantics, strings, mappings, or foreign array subclasses.
    if type(value) not in (tuple, list):
        raise ShapeContractError(f"{name} must be a list or tuple")
    return tuple(value)


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ShapeContractError("invalid canonical JSON data") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("ascii")).hexdigest()


def _hex(value: Any, name: str) -> float:
    if type(value) is not str:
        raise ShapeContractError(f"{name} must be a canonical float.hex string")
    try:
        number = float.fromhex(value)
    except (ValueError, OverflowError) as exc:
        raise ShapeContractError(f"invalid {name}") from exc
    _finite(number, name)
    if number.hex() != value:
        raise ShapeContractError(f"noncanonical {name}")
    return number


def _object(value: Any, keys: set[str], name: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ShapeContractError(f"{name} has missing or unknown fields")
    return value


def _document_tree(value: Any) -> None:
    """Require JSON-native canonical containers and integer numeric fields."""
    try:
        if type(value) is dict:
            for key, item in value.items():
                if type(key) is not str:
                    raise ShapeContractError("JSON field names must be strings")
                _document_tree(item)
        elif type(value) is list:
            for item in value:
                _document_tree(item)
        elif type(value) not in (str, int):
            raise ShapeContractError("serialized fields require canonical JSON types")
    except RecursionError as exc:
        raise ShapeContractError("serialization nesting is invalid") from exc


def _load_json(payload: str) -> dict:
    if type(payload) is not str or len(payload) > 8_000_000:
        raise ShapeContractError("serialization must be a string of at most 8 MB")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ShapeContractError(f"duplicate JSON field: {key}")
            result[key] = value
        return result

    def no_constant(value):
        raise ShapeContractError(f"nonfinite JSON constant: {value}")

    try:
        result = json.loads(payload, object_pairs_hook=unique, parse_constant=no_constant)
    except (ValueError, RecursionError) as exc:
        raise ShapeContractError("invalid JSON serialization") from exc
    if type(result) is not dict:
        raise ShapeContractError("serialization must contain a JSON object")
    return result


def _coordinates(value: Any, n: int) -> tuple[tuple[float, float, float], ...]:
    rows = _sequence(value, "coordinates")
    if len(rows) != n:
        raise ShapeDomainError("coordinate count does not match ordered atom IDs")
    result = []
    for row in rows:
        xyz = _sequence(row, "coordinate row")
        if len(xyz) != 3:
            raise ShapeDomainError("coordinates must have shape (N, 3)")
        result.append(tuple(_number(v, "coordinate") for v in xyz))
    return tuple(result)


def _distance(a: tuple, b: tuple) -> tuple[float, tuple[float, float, float]]:
    delta = tuple(_finite(x - y, "coordinate difference") for x, y in zip(a, b))
    # hypot avoids *introducing* square overflow for a representable distance.
    distance = _finite(math.hypot(*delta), "pair distance")
    if distance < MIN_DISTANCE:
        raise ShapeDomainError(f"pair distance is below {MIN_DISTANCE} Angstrom")
    return distance, delta


@dataclass(frozen=True, slots=True)
class MoleculeIdentity:
    """Exact canonical source atom order and a single connected covalent graph.

    Bonds are ordered (i, j, source_bond_kind) triples, with i < j and increasing
    (i, j). Kind is an opaque nonempty source descriptor (e.g. 'single'). The
    canonical molecule string must come from the admitted source; no chemistry
    parser or stereochemical inference is performed here.
    """
    atom_ids: tuple[str, ...]
    elements: tuple[str, ...]
    covalent_bonds: tuple[tuple[int, int, str], ...]
    canonical_molecule: str
    molecular_digest: str = field(init=False)
    topology_digest: str = field(init=False)

    def __post_init__(self):
        ids = _sequence(self.atom_ids, "atom IDs")
        n = len(ids)
        if not 2 <= n <= MAX_ATOMS:
            raise ShapeContractError("atom count must be between 2 and 256")
        ids = tuple(_text(v, "atom ID") for v in ids)
        if len(set(ids)) != n:
            raise ShapeContractError("atom IDs must be unique")
        elements = _sequence(self.elements, "elements")
        if len(elements) != n or any(type(e) is not str or e not in _ELEMENTS for e in elements):
            raise ShapeContractError("one valid element symbol is required per atom")
        bonds = []
        graph = [set() for _ in range(n)]
        previous = (-1, -1)
        for raw in _sequence(self.covalent_bonds, "covalent bonds"):
            edge = _sequence(raw, "covalent bond")
            if len(edge) != 3:
                raise ShapeContractError("bonds must be (i, j, kind) triples")
            i, j, kind = edge
            if type(i) is not int or type(j) is not int or not 0 <= i < j < n:
                raise ShapeContractError("bond indices must be integers with 0 <= i < j < N")
            if (i, j) <= previous:
                raise ShapeContractError("bonds must be unique and in canonical pair order")
            kind = _text(kind, "bond kind")
            previous = (i, j)
            bonds.append((i, j, kind))
            graph[i].add(j)
            graph[j].add(i)
        seen, pending = {0}, [0]
        while pending:
            for neighbor in graph[pending.pop()]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    pending.append(neighbor)
        if len(seen) != n:
            raise ShapeContractError("ligand covalent graph must be connected")
        molecule = _text(self.canonical_molecule, "canonical molecular identifier")
        object.__setattr__(self, "atom_ids", ids)
        object.__setattr__(self, "elements", tuple(elements))
        object.__setattr__(self, "covalent_bonds", tuple(bonds))
        object.__setattr__(self, "canonical_molecule", molecule)
        object.__setattr__(self, "molecular_digest", _digest({"canonical_molecule": molecule}))
        object.__setattr__(self, "topology_digest", _digest(self._topology_document()))

    def _topology_document(self) -> dict:
        return {"atom_ids": list(self.atom_ids), "elements": list(self.elements),
                "covalent_bonds": [list(b) for b in self.covalent_bonds]}

    def _document(self) -> dict:
        return {**self._topology_document(), "canonical_molecule": self.canonical_molecule,
                "molecular_digest": self.molecular_digest, "topology_digest": self.topology_digest}

    def validate_integrity(self) -> None:
        try:
            if (type(self) is not MoleculeIdentity or type(self.atom_ids) is not tuple
                    or type(self.elements) is not tuple or type(self.covalent_bonds) is not tuple
                    or any(type(b) is not tuple for b in self.covalent_bonds)):
                raise ShapeContractError("identity storage must be immutable")
            _sha(self.molecular_digest, "molecular digest")
            _sha(self.topology_digest, "topology digest")
            rebuilt = MoleculeIdentity(self.atom_ids, self.elements, self.covalent_bonds,
                                       self.canonical_molecule)
            if _json(self._document()) != _json(rebuilt._document()):
                raise ShapeContractError("molecular identity has been mutated or forged")
        except (AttributeError, TypeError, OverflowError) as exc:
            raise ShapeContractError("incomplete or forged molecular identity") from exc

    @classmethod
    def _from_document(cls, doc: dict) -> MoleculeIdentity:
        _object(doc, {"atom_ids", "elements", "covalent_bonds", "canonical_molecule",
                      "molecular_digest", "topology_digest"}, "identity")
        identity = cls(doc["atom_ids"], doc["elements"], doc["covalent_bonds"], doc["canonical_molecule"])
        if _json(identity._document()) != _json(doc):
            raise ShapeContractError("identity fields or digests are noncanonical")
        return identity


@dataclass(frozen=True, slots=True)
class ShapeReference:
    identity: MoleculeIdentity
    coordinates: tuple[tuple[float, float, float], ...]
    parent_provenance: str
    source_identity: str
    source_digest: str
    parent_role: str = PARENT_ROLE
    pairs: tuple[tuple[int, int], ...] = field(init=False)
    distances: tuple[float, ...] = field(init=False)
    coordinates_digest: str = field(init=False)
    digest: str = field(init=False)

    def __post_init__(self):
        if type(self.identity) is not MoleculeIdentity:
            raise ShapeContractError("reference requires an exact MoleculeIdentity")
        self.identity.validate_integrity()
        # Copy the identity as well as its primitive containers.
        identity = MoleculeIdentity(self.identity.atom_ids, self.identity.elements,
                                    self.identity.covalent_bonds, self.identity.canonical_molecule)
        coords = _coordinates(self.coordinates, len(identity.atom_ids))
        if self.parent_role != PARENT_ROLE or type(self.parent_role) is not str:
            raise ShapeContractError("reference must have the original supplied parent role")
        _text(self.parent_provenance, "parent provenance")
        _text(self.source_identity, "source identity")
        _sha(self.source_digest, "source digest")
        pairs = tuple((i, j) for i in range(len(coords)) for j in range(i + 1, len(coords)))
        distances = tuple(_distance(coords[i], coords[j])[0] for i, j in pairs)
        object.__setattr__(self, "identity", identity)
        object.__setattr__(self, "coordinates", coords)
        object.__setattr__(self, "pairs", pairs)
        object.__setattr__(self, "distances", distances)
        object.__setattr__(self, "coordinates_digest", _digest([[v.hex() for v in xyz] for xyz in coords]))
        object.__setattr__(self, "digest", _digest(self._body()))

    def _body(self) -> dict:
        return {
            "schema_id": SCHEMA, "identity": self.identity._document(),
            "coordinates_binary64": [[v.hex() for v in xyz] for xyz in self.coordinates],
            "coordinates_digest": self.coordinates_digest,
            "parent_role": self.parent_role, "parent_provenance": self.parent_provenance,
            "source_identity": self.source_identity, "source_digest": self.source_digest,
            "atom_count": len(self.identity.atom_ids), "pair_count": len(self.pairs),
            "pairs": [list(p) for p in self.pairs],
            "reference_distances_binary64": [v.hex() for v in self.distances],
            "pair_selection": PAIR_POLICY, "normalization": NORMALIZATION,
            "minimum_distance_binary64": MIN_DISTANCE.hex(),
            "units": {"coordinates": "angstrom", "energy": "kcal/mol",
                      "force": "kcal/mol/angstrom", "strength": "kcal/mol/angstrom^2"},
        }

    def validate_integrity(self) -> None:
        try:
            if (type(self) is not ShapeReference or type(self.identity) is not MoleculeIdentity
                    or type(self.coordinates) is not tuple
                    or any(type(row) is not tuple or any(type(v) is not float for v in row)
                           for row in self.coordinates)
                    or type(self.pairs) is not tuple or any(type(p) is not tuple for p in self.pairs)
                    or type(self.distances) is not tuple or any(type(v) is not float for v in self.distances)):
                raise ShapeContractError("reference storage must be immutable binary64 values")
            _sha(self.digest, "reference digest")
            _sha(self.coordinates_digest, "coordinate digest")
            self.identity.validate_integrity()
            rebuilt = ShapeReference(self.identity, self.coordinates, self.parent_provenance,
                                     self.source_identity, self.source_digest, self.parent_role)
            if self.digest != rebuilt.digest or _json(self._body()) != _json(rebuilt._body()):
                raise ShapeContractError("reference has been mutated or forged")
        except (AttributeError, TypeError, OverflowError) as exc:
            raise ShapeContractError("incomplete or forged reference") from exc

    def to_document(self) -> dict:
        self.validate_integrity()
        return {**self._body(), "digest": self.digest}

    def to_json(self) -> str:
        return _json(self.to_document())

    @classmethod
    def from_document(cls, document: dict, *, expected_digest: str) -> ShapeReference:
        _sha(expected_digest, "trusted reference digest")
        _document_tree(document)
        keys = {"schema_id", "identity", "coordinates_binary64", "coordinates_digest",
                "parent_role", "parent_provenance", "source_identity", "source_digest",
                "atom_count", "pair_count", "pairs", "reference_distances_binary64",
                "pair_selection", "normalization", "minimum_distance_binary64", "units", "digest"}
        doc = _object(document, keys, "reference")
        _sha(doc["digest"], "reference digest")
        if doc["digest"] != expected_digest:
            raise ShapeContractError("reference digest does not match trusted identity")
        if _digest({k: v for k, v in doc.items() if k != "digest"}) != doc["digest"]:
            raise ShapeContractError("reference serialization digest mismatch")
        identity = MoleculeIdentity._from_document(doc["identity"])
        coords = tuple(tuple(_hex(v, "coordinate") for v in _sequence(row, "coordinate row"))
                       for row in _sequence(doc["coordinates_binary64"], "coordinates"))
        reference = cls(identity, coords, doc["parent_provenance"], doc["source_identity"],
                        doc["source_digest"], doc["parent_role"])
        # Exact canonical equality validates all fixed fields, integer types,
        # complete/unique/ordered pairs, pair targets, units, and derived digests.
        if _json(reference.to_document()) != _json(doc):
            raise ShapeContractError("reference fields are inconsistent or noncanonical")
        return reference

    @classmethod
    def from_json(cls, payload: str, *, expected_digest: str) -> ShapeReference:
        return cls.from_document(_load_json(payload), expected_digest=expected_digest)


class ShapeEvaluation(NamedTuple):
    energy: float
    forces: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True, slots=True)
class ShapeContract:
    """Frozen strength and original reference, to bind once per opt-in arm."""
    reference: ShapeReference
    strength: float
    reference_digest: str = field(init=False)
    digest: str = field(init=False)

    def __post_init__(self):
        if type(self.reference) is not ShapeReference:
            raise ShapeContractError("contract requires an exact ShapeReference")
        self.reference.validate_integrity()
        strength = _number(self.strength, "strength")
        if strength not in STRENGTHS or (strength == 0 and math.copysign(1.0, strength) < 0):
            raise ShapeContractError("strength must be exactly 0, 100, or 1000")
        # Independent defensive copy prevents even object.__setattr__ on a
        # caller's reference from changing this contract's original reference.
        reference = ShapeReference.from_json(self.reference.to_json(), expected_digest=self.reference.digest)
        object.__setattr__(self, "reference", reference)
        object.__setattr__(self, "strength", strength)
        object.__setattr__(self, "reference_digest", reference.digest)
        object.__setattr__(self, "digest", _digest(self._body()))

    def _body(self) -> dict:
        return {"schema_id": CONTRACT_SCHEMA, "reference_digest": self.reference_digest,
                "strength_binary64": self.strength.hex(), "reference": self.reference.to_document()}

    def validate_integrity(self) -> None:
        try:
            if (type(self) is not ShapeContract or type(self.reference) is not ShapeReference
                    or type(self.strength) is not float):
                raise ShapeContractError("incomplete or forged contract")
            if self.strength not in STRENGTHS or (self.strength == 0 and math.copysign(1.0, self.strength) < 0):
                raise ShapeContractError("invalid contract strength")
            _sha(self.digest, "contract digest")
            _sha(self.reference_digest, "bound reference digest")
            self.reference.validate_integrity()
            if self.reference_digest != self.reference.digest or self.digest != _digest(self._body()):
                raise ShapeContractError("contract has been mutated or forged")
        except (AttributeError, TypeError, OverflowError) as exc:
            raise ShapeContractError("incomplete or forged contract") from exc

    def to_document(self) -> dict:
        self.validate_integrity()
        return {**self._body(), "digest": self.digest}

    def to_json(self) -> str:
        return _json(self.to_document())

    @classmethod
    def from_document(cls, document: dict, *, expected_digest: str) -> ShapeContract:
        _sha(expected_digest, "trusted contract digest")
        _document_tree(document)
        doc = _object(document, {"schema_id", "reference_digest", "strength_binary64", "reference", "digest"}, "contract")
        if doc["digest"] != expected_digest:
            raise ShapeContractError("contract digest does not match trusted identity")
        reference = ShapeReference.from_document(doc["reference"], expected_digest=doc["reference_digest"])
        contract = cls(reference, _hex(doc["strength_binary64"], "strength"))
        if _json(contract.to_document()) != _json(doc):
            raise ShapeContractError("contract fields or digest are inconsistent or noncanonical")
        return contract

    @classmethod
    def from_json(cls, payload: str, *, expected_digest: str) -> ShapeContract:
        return cls.from_document(_load_json(payload), expected_digest=expected_digest)

    def evaluate(self, coordinates: Any, *, identity: MoleculeIdentity) -> ShapeEvaluation:
        """Return the analytic penalty and negative gradient; dispatch no base work."""
        self.validate_integrity()
        if type(identity) is not MoleculeIdentity:
            raise ShapeContractError("trial requires an exact MoleculeIdentity")
        identity.validate_integrity()
        if _json(identity._document()) != _json(self.reference.identity._document()):
            raise ShapeContractError("trial atom order or molecular/topology identity changed")
        n = len(identity.atom_ids)
        if self.strength == 0.0:
            return ShapeEvaluation(0.0, tuple((0.0, 0.0, 0.0) for _ in range(n)))
        xyz = _coordinates(coordinates, n)
        scale = self.strength / len(self.reference.pairs)
        squared_deviations = []
        force_terms = [[[], [], []] for _ in range(n)]
        for (i, j), target in zip(self.reference.pairs, self.reference.distances):
            distance, delta = _distance(xyz[i], xyz[j])
            deviation = _finite(distance - target, "distance deviation")
            squared_deviations.append(_finite(deviation * deviation, "squared distance deviation"))
            magnitude = _finite(-scale * deviation, "pair force magnitude")
            for axis in range(3):
                component = _finite(magnitude * (delta[axis] / distance), "pair force component")
                force_terms[i][axis].append(component)
                force_terms[j][axis].append(-component)
        try:
            total_squared = _finite(math.fsum(squared_deviations), "sum of squared deviations")
            energy = _finite((scale / 2.0) * total_squared, "shape energy")
            forces = tuple(tuple(_finite(math.fsum(terms), "summed force component")
                                 for terms in atom) for atom in force_terms)
        except OverflowError as exc:
            raise ShapeDomainError("overflow in energy or force summation") from exc
        return ShapeEvaluation(energy, forces)


def evaluate_shape(contract: ShapeContract, coordinates: Any, *, identity: MoleculeIdentity) -> ShapeEvaluation:
    """Functional adapter entrypoint; rejects duck-typed or subclassed contracts."""
    if type(contract) is not ShapeContract:
        raise ShapeContractError("an exact ShapeContract is required")
    return contract.evaluate(coordinates, identity=identity)
