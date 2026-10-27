"""Opt-in bounded rigid/bridge-torsion energy refinement.

Pure Python geometry, not chemistry perception or scientific admission. A caller
must supply an authenticated topology/rotor policy and a qualified E/F evaluator.
The numerical method uses fresh local retractions, not a fixed rotation chart:
world torque is the derivative only at each current state's zero increment.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Sequence

Vector = tuple[float, float, float]
Coordinates = tuple[Vector, ...]
MAX_ATOMS = 512
MAX_ROTORS = 128
ALGORITHM_ID = "structure_preserving_block_retraction/1.1.0"


class StructureSearchError(ValueError):
    """Invalid geometry, topology, or numerical policy (never raw backend text)."""


RECOVERABLE_TRIAL_REASONS = frozenset({"coordinate_domain_singularity"})


class RecoverableTrialRejection(Exception):
    """Explicit provider geometric-domain rejection, never arbitrary backend text.

    Identity, model and parameter validation must precede this signal. It does
    not classify generic evaluator exceptions or authorize physical execution.
    """

    def __init__(self, reason_code: str):
        if type(reason_code) is not str or reason_code not in RECOVERABLE_TRIAL_REASONS:
            raise StructureSearchError("invalid recoverable trial reason")
        self.reason_code = reason_code
        super().__init__(reason_code)


def _number(value: object) -> float:
    if type(value) not in (int, float):
        raise StructureSearchError("expected a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise StructureSearchError("expected a finite number") from None
    if not math.isfinite(result):
        raise StructureSearchError("expected a finite number")
    return result


def _vector(value: Sequence[float]) -> Vector:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise StructureSearchError("expected a three-component vector")
    return tuple(_number(x) for x in value)  # type: ignore[return-value]


def _coordinates(value: Sequence[Sequence[float]], count: int | None = None) -> Coordinates:
    if not isinstance(value, (tuple, list)) or not 1 <= len(value) <= MAX_ATOMS:
        raise StructureSearchError("coordinate count is outside the supported bound")
    if count is not None and len(value) != count:
        raise StructureSearchError("coordinate/topology count mismatch")
    result = tuple(_vector(row) for row in value)
    if any(abs(x) > 1.e6 for row in result for x in row):
        raise StructureSearchError("coordinate magnitude exceeds numerical scope")
    return result


def _add(a: Vector, b: Vector) -> Vector:
    return _vector(tuple(x + y for x, y in zip(a, b)))


def _sub(a: Vector, b: Vector) -> Vector:
    return _vector(tuple(x - y for x, y in zip(a, b)))


def _scale(a: Vector, value: float) -> Vector:
    return _vector(tuple(x * value for x in a))


def _dot(a: Vector, b: Vector) -> float:
    try:
        return _number(math.fsum(x * y for x, y in zip(a, b)))
    except (OverflowError, ValueError):
        raise StructureSearchError("nonfinite scalar reduction") from None


def _cross(a: Vector, b: Vector) -> Vector:
    return _vector((a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]))


def _norm(a: Vector) -> float:
    return _number(math.hypot(*a))


def _sum_vectors(rows: Sequence[Vector]) -> Vector:
    try:
        return _vector(tuple(math.fsum(row[k] for row in rows) for k in range(3)))
    except (OverflowError, ValueError):
        raise StructureSearchError("nonfinite vector reduction") from None


def centroid(coordinates: Coordinates) -> Vector:
    points = _coordinates(coordinates)
    # Reference-relative accumulation avoids unnecessary large-origin sums.
    anchor = points[0]
    relative = tuple(_sub(p, anchor) for p in points)
    return _add(anchor, _scale(_sum_vectors(relative), 1.0 / len(points)))


@dataclass(frozen=True)
class StructureTopology:
    """Explicit covalent graph and caller-authorized oriented rotor bonds.

    ``bonds`` are (i, j, kind), where kind is single/double/triple/aromatic/
    amide/other. Only explicitly listed single, non-ring edges may rotate.
    The complete b-side component is derived, never supplied as a partial mask.
    This limited contract accepts one connected component, at most 512 atoms.
    """
    atom_count: int
    bonds: tuple[tuple[int, int, str], ...]
    rotatable_bonds: tuple[tuple[int, int], ...] = ()

    def __post_init__(self) -> None:
        if type(self.atom_count) is not int or not 1 <= self.atom_count <= MAX_ATOMS:
            raise StructureSearchError("invalid atom count")
        if not isinstance(self.bonds, (tuple, list)) or len(self.bonds) > 4 * self.atom_count:
            raise StructureSearchError("invalid bond collection")
        kinds = {"single", "double", "triple", "aromatic", "amide", "other"}
        edges: dict[tuple[int, int], str] = {}
        adjacency = [set() for _ in range(self.atom_count)]
        for bond in self.bonds:
            if not isinstance(bond, (tuple, list)) or len(bond) != 3:
                raise StructureSearchError("invalid bond row")
            a, b, kind = bond
            if (type(a) is not int or type(b) is not int or not 0 <= a < self.atom_count
                    or not 0 <= b < self.atom_count or a == b or type(kind) is not str or kind not in kinds):
                raise StructureSearchError("invalid bond declaration")
            edge = tuple(sorted((a, b)))
            if edge in edges:
                raise StructureSearchError("duplicate covalent bond")
            edges[edge] = kind
            adjacency[a].add(b)
            adjacency[b].add(a)
        seen = {0}
        queue = [0]
        for a in queue:
            for b in sorted(adjacency[a] - seen):
                seen.add(b)
                queue.append(b)
        if len(seen) != self.atom_count:
            raise StructureSearchError("disconnected topology is outside this scope")
        if not isinstance(self.rotatable_bonds, (tuple, list)) or len(self.rotatable_bonds) > MAX_ROTORS:
            raise StructureSearchError("invalid rotor collection")
        rotors = []
        rotor_edges = set()
        for rotor in self.rotatable_bonds:
            if not isinstance(rotor, (tuple, list)) or len(rotor) != 2:
                raise StructureSearchError("invalid rotor row")
            a, b = rotor
            if type(a) is not int or type(b) is not int:
                raise StructureSearchError("invalid rotor indices")
            edge = tuple(sorted((a, b)))
            if edges.get(edge) != "single" or edge in rotor_edges:
                raise StructureSearchError("rotor is not a unique declared single bond")
            rotor_edges.add(edge)
            rotors.append((a, b))
        object.__setattr__(self, "bonds", tuple((a, b, kind) for (a, b), kind in sorted(edges.items())))
        object.__setattr__(self, "rotatable_bonds", tuple(rotors))
        for rotor_index in range(len(rotors)):
            self.moving_atoms(rotor_index)

    def moving_atoms(self, rotor_index: int) -> tuple[int, ...]:
        if type(rotor_index) is not int or not 0 <= rotor_index < len(self.rotatable_bonds):
            raise StructureSearchError("invalid rotor index")
        a, b = self.rotatable_bonds[rotor_index]
        adjacency = [set() for _ in range(self.atom_count)]
        for i, j, _ in self.bonds:
            if {i, j} != {a, b}:
                adjacency[i].add(j)
                adjacency[j].add(i)
        seen, queue = {b}, [b]
        for node in queue:
            for other in sorted(adjacency[node] - seen):
                seen.add(other)
                queue.append(other)
        if a in seen:
            raise StructureSearchError("ring bonds cannot be torsion rotors")
        return tuple(sorted(seen))


def _rotate_relative(value: Vector, unit: Vector, angle: float) -> Vector:
    c, s = math.cos(angle), math.sin(angle)
    return _add(_add(_scale(value, c), _scale(_cross(unit, value), s)),
                _scale(unit, _dot(unit, value) * (1.0 - c)))


def rigid_move(coordinates: Coordinates, *, translation: Vector = (0., 0., 0.),
               rotation: Vector = (0., 0., 0.), pivot: Vector | None = None) -> Coordinates:
    """World-frame rotation-vector increment in radians, followed by translation."""
    points = _coordinates(coordinates)
    shift, increment = _vector(translation), _vector(rotation)
    origin = centroid(points) if pivot is None else _vector(pivot)
    angle = _norm(increment)
    if angle > math.pi:
        raise StructureSearchError("rotation increment exceeds pi radians")
    if angle == 0.0:
        return _coordinates(tuple(_add(p, shift) for p in points))
    axis = _scale(increment, 1.0 / angle)
    return _coordinates(tuple(_add(_add(origin, _rotate_relative(_sub(p, origin), axis, angle)), shift)
                              for p in points))


def torsion_move(coordinates: Coordinates, topology: StructureTopology,
                 rotor_index: int, angle: float) -> Coordinates:
    """Rotate the entire b-side bridge component around the CURRENT a→b axis."""
    if type(topology) is not StructureTopology:
        raise StructureSearchError("invalid topology")
    points = _coordinates(coordinates, topology.atom_count)
    moved = set(topology.moving_atoms(rotor_index))
    increment = _number(angle)
    if abs(increment) > math.pi:
        raise StructureSearchError("torsion increment exceeds pi radians")
    a, b = topology.rotatable_bonds[rotor_index]
    axis = _sub(points[b], points[a])
    length = _norm(axis)
    if length <= 1.e-10:
        raise StructureSearchError("degenerate torsion axis")
    unit = _scale(axis, 1.0 / length)
    # Keep both axis atoms exact rather than accumulating roundoff on them.
    return _coordinates(tuple(_add(points[a], _rotate_relative(_sub(p, points[a]), unit, increment))
                              if i in moved and i != b else p for i, p in enumerate(points)))


@dataclass(frozen=True)
class ProjectedForces:
    translation: Vector
    rotation: Vector
    torsions: tuple[float, ...]


def project_forces(coordinates: Coordinates, forces: Coordinates,
                   topology: StructureTopology) -> ProjectedForces:
    """Pull back raw physical forces at a fresh local chart (zero increment).

    Translation has energy/Angstrom units; rotation and torsion energy/radian.
    These are negative derivatives, NOT a Cartesian convergence certificate.
    """
    if type(topology) is not StructureTopology:
        raise StructureSearchError("invalid topology")
    points = _coordinates(coordinates, topology.atom_count)
    if not isinstance(forces, (tuple, list)) or len(forces) != len(points):
        raise StructureSearchError("force count mismatch")
    force = tuple(_vector(row) for row in forces)
    center = centroid(points)
    translation = _sum_vectors(force)
    rotation = _sum_vectors(tuple(_cross(_sub(p, center), f) for p, f in zip(points, force)))
    torsions = []
    for rotor_index, (a, b) in enumerate(topology.rotatable_bonds):
        direction = _sub(points[b], points[a])
        length = _norm(direction)
        if length <= 1.e-10:
            raise StructureSearchError("degenerate torsion axis")
        unit = _scale(direction, 1.0 / length)
        try:
            q = math.fsum(_dot(force[i], _cross(unit, _sub(points[i], points[a])))
                          for i in topology.moving_atoms(rotor_index) if i != b)
        except (OverflowError, ValueError):
            raise StructureSearchError("nonfinite torsion force") from None
        torsions.append(_number(q))
    return ProjectedForces(translation, rotation, tuple(torsions))


@dataclass(frozen=True)
class Evaluation:
    energy: float
    forces: Coordinates

    def __post_init__(self) -> None:
        object.__setattr__(self, "energy", _number(self.energy))
        if not isinstance(self.forces, (tuple, list)) or not 1 <= len(self.forces) <= MAX_ATOMS:
            raise StructureSearchError("invalid evaluation force count")
        object.__setattr__(self, "forces", tuple(_vector(row) for row in self.forces))


@dataclass(frozen=True)
class SearchConfig:
    max_steps: int = 64
    max_evaluations: int = 256
    max_backtracks: int = 8
    translation_step_angstrom: float = 0.10
    rotation_step_radians: float = 0.10
    torsion_step_radians: float = 0.10
    max_total_translation_angstrom: float = 2.0
    max_total_rotation_radians: float = math.pi
    max_total_torsion_radians: float = math.pi
    translation_force_tolerance: float = 1.e-6
    angular_force_tolerance: float = 1.e-6
    armijo: float = 1.e-4

    def __post_init__(self) -> None:
        for name, bound in (("max_steps", 1024), ("max_evaluations", 16384), ("max_backtracks", 24)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= bound:
                raise StructureSearchError("invalid search work bound")
        for name, upper in (("translation_step_angstrom", 1.), ("rotation_step_radians", math.pi/2),
                            ("torsion_step_radians", math.pi/2)):
            value = _number(getattr(self, name))
            if not 0. < value <= upper:
                raise StructureSearchError("invalid move bound")
            object.__setattr__(self, name, value)
        for name in ("translation_force_tolerance", "angular_force_tolerance"):
            value = _number(getattr(self, name))
            if not 0. < value <= 1.:
                raise StructureSearchError("invalid projected-force tolerance")
            object.__setattr__(self, name, value)
        for name, step, upper in (("max_total_translation_angstrom", "translation_step_angstrom", 20.),
                                  ("max_total_rotation_radians", "rotation_step_radians", 2*math.pi),
                                  ("max_total_torsion_radians", "torsion_step_radians", 2*math.pi)):
            value = _number(getattr(self, name))
            if not getattr(self, step) <= value <= upper:
                raise StructureSearchError("invalid cumulative motion bound")
            object.__setattr__(self, name, value)
        value = _number(self.armijo)
        if not 0. < value < 0.5:
            raise StructureSearchError("invalid sufficient-decrease coefficient")
        object.__setattr__(self, "armijo", value)


@dataclass(frozen=True)
class SearchStep:
    evaluation_index: int
    move: str
    backtrack: int
    energy: float | None
    status: str
    reason_code: str | None = None


@dataclass(frozen=True)
class SearchResult:
    coordinates: Coordinates
    initial_energy: float | None
    energy: float | None
    forces: Coordinates | None
    status: str
    accepted_steps: int
    evaluation_attempts: int
    successful_evaluations: int
    failed_evaluations: int
    history: tuple[SearchStep, ...]
    projected_forces: ProjectedForces | None
    recoverable_rejections: int = 0

    @property
    def projected_stationary(self) -> bool:
        return self.status == "projected_stationary"


def _bond_lengths(points: Coordinates, topology: StructureTopology) -> tuple[float, ...]:
    return tuple(_norm(_sub(points[b], points[a])) for a, b, _ in topology.bonds)


def refine_structure(coordinates: Coordinates, topology: StructureTopology,
                     evaluate: Callable[[Coordinates], Evaluation],
                     config: SearchConfig | None = None) -> SearchResult:
    """Monotone bounded block-coordinate refinement in structure-preserving DOFs.

    Picks the block with largest first-order decrease at its configured step
    bound, then halves that step until Armijo decrease. Every callback invocation
    (initial, accepted, rejected, malformed, failed) consumes one budget slot.
    These are callback attempts, not a claim about physical backend kernel/E/F
    counts. A callback must evaluate the supplied coordinates without stale
    cache reuse and owns its qualified physical evaluation and work accounting.
    Only exact typed RecoverableTrialRejection with a whitelisted reason retries
    a trial at half step. Initial rejection has no accepted state. All other
    exceptions terminate with sanitized failure status and last accepted state.
    Recoverable rejections are a subset of failed_evaluations; every invocation
    satisfies evaluation_attempts = successful_evaluations + failed_evaluations.
    On any rejected trial, exhausted callback budget takes precedence over the
    backtrack limit. Hard callback failure still terminates as evaluation_failed.
    There is no optimizer history, no hidden final evaluation, and no restart.
    """
    if type(topology) is not StructureTopology or not callable(evaluate):
        raise StructureSearchError("invalid refinement inputs")
    policy = SearchConfig() if config is None else config
    if type(policy) is not SearchConfig:
        raise StructureSearchError("invalid search configuration")
    current = _coordinates(coordinates, topology.atom_count)
    original_lengths = _bond_lengths(current, topology)
    if any(length <= 1.e-10 for length in original_lengths):
        raise StructureSearchError("degenerate covalent geometry")
    # Validate all axes before any backend call.
    project_forces(current, tuple((0., 0., 0.) for _ in current), topology)
    history: list[SearchStep] = []
    attempted = successful = failed = accepted = recoverable = 0
    initial_energy: float | None = None
    observation: Evaluation | None = None
    projected: ProjectedForces | None = None
    translation_path = rotation_path = 0.0
    torsion_paths = [0.0] * len(topology.rotatable_bonds)

    def finish(status: str) -> SearchResult:
        return SearchResult(current, initial_energy, None if observation is None else observation.energy,
                            None if observation is None else observation.forces, status, accepted,
                            attempted, successful, failed, tuple(history), projected, recoverable)

    def call(points: Coordinates, move: str, backtrack: int) -> Evaluation | RecoverableTrialRejection | None:
        nonlocal attempted, successful, failed, recoverable
        attempted += 1
        try:
            result = evaluate(points)
            if type(result) is not Evaluation or len(result.forces) != topology.atom_count:
                raise StructureSearchError("invalid callback evaluation")
            # Revalidate even a frozen object forged through low-level mutation.
            result = Evaluation(result.energy, result.forces)
        except RecoverableTrialRejection as rejection:
            failed += 1
            reason = (getattr(rejection, "reason_code", None)
                      if type(rejection) is RecoverableTrialRejection else None)
            if (type(rejection) is RecoverableTrialRejection and type(reason) is str
                    and reason in RECOVERABLE_TRIAL_REASONS):
                recoverable += 1
                history.append(SearchStep(attempted, move, backtrack, None,
                                          "recoverable_trial_rejection", reason))
                return rejection
            history.append(SearchStep(attempted, move, backtrack, None, "evaluation_failed"))
            return None
        except Exception:
            failed += 1
            history.append(SearchStep(attempted, move, backtrack, None, "evaluation_failed"))
            return None
        successful += 1
        return result

    initial = call(current, "initial", 0)
    if type(initial) is not Evaluation:
        return finish("evaluation_failed")
    observation = initial
    initial_energy = observation.energy
    history.append(SearchStep(attempted, "initial", 0, observation.energy, "initial"))
    while True:
        try:
            projected = None
            projected = project_forces(current, observation.forces, topology)
            tnorm, rnorm = _norm(projected.translation), _norm(projected.rotation)
            tmax = max((abs(q) for q in projected.torsions), default=0.)
            if (tnorm <= policy.translation_force_tolerance and
                    max(rnorm, tmax) <= policy.angular_force_tolerance):
                return finish("projected_stationary")
            if accepted >= policy.max_steps:
                return finish("step_limit")
            if attempted >= policy.max_evaluations:
                return finish("evaluation_limit")
            translation_step = min(policy.translation_step_angstrom,
                                   max(0., policy.max_total_translation_angstrom - translation_path))
            rotation_step = min(policy.rotation_step_radians,
                                max(0., policy.max_total_rotation_radians - rotation_path))
            torsion_steps = [min(policy.torsion_step_radians,
                                max(0., policy.max_total_torsion_radians - path)) for path in torsion_paths]
            options = [(tnorm * translation_step if tnorm > policy.translation_force_tolerance else 0.,
                        "translation", -1, translation_step),
                       (rnorm * rotation_step if rnorm > policy.angular_force_tolerance else 0.,
                        "rotation", -1, rotation_step)]
            options.extend((abs(q) * torsion_steps[index] if abs(q) > policy.angular_force_tolerance else 0.,
                            "torsion", index, torsion_steps[index])
                           for index, q in enumerate(projected.torsions))
            # Stable ordering: translation, rotation, then authority rotor order.
            gain, kind, rotor, step = max(options, key=lambda item: item[0])
            gain = _number(gain)
            if gain <= 0.:
                return finish("motion_limit")
            for backtrack in range(policy.max_backtracks + 1):
                if attempted >= policy.max_evaluations:
                    return finish("evaluation_limit")
                scale = 2. ** -backtrack
                if kind == "translation":
                    trial = rigid_move(current, translation=_scale(projected.translation,
                                       step * scale / tnorm))
                elif kind == "rotation":
                    trial = rigid_move(current, rotation=_scale(projected.rotation,
                                       step * scale / rnorm))
                else:
                    trial = torsion_move(current, topology, rotor,
                                         math.copysign(step * scale,
                                                       projected.torsions[rotor]))
                lengths = _bond_lengths(trial, topology)
                if any(abs(a-b) > 1.e-8 * max(1., a) for a, b in zip(original_lengths, lengths)):
                    return finish("geometry_failure")
                if trial == current:
                    return finish("no_representable_step")
                tested = call(trial, kind if rotor < 0 else f"torsion:{rotor}", backtrack)
                if tested is None:
                    return finish("evaluation_failed")
                if type(tested) is RecoverableTrialRejection:
                    if attempted >= policy.max_evaluations:
                        return finish("evaluation_limit")
                    continue
                required = policy.armijo * scale * gain
                decrease = observation.energy - tested.energy
                if math.isfinite(decrease) and decrease > 0. and decrease >= required:
                    history.append(SearchStep(attempted, kind if rotor < 0 else f"torsion:{rotor}",
                                              backtrack, tested.energy, "accepted"))
                    current, observation = trial, tested
                    accepted += 1
                    if kind == "translation":
                        translation_path += step * scale
                    elif kind == "rotation":
                        rotation_path += step * scale
                    else:
                        torsion_paths[rotor] += step * scale
                    break
                history.append(SearchStep(attempted, kind if rotor < 0 else f"torsion:{rotor}",
                                          backtrack, tested.energy, "rejected"))
                if attempted >= policy.max_evaluations:
                    return finish("evaluation_limit")
            else:
                return finish("line_search_failed")
        except (StructureSearchError, OverflowError, ValueError):
            return finish("numerical_failure")
