"""Receptor-frame, source-bound pose labels; never an objective or pose selector.

The caller freezes source admission, atom maps and the metric policy before
using real coordinates. This module verifies array/map contracts, not chemical
graph identity or the authenticity of caller-supplied source digests. Geometry
and contact diagnostics may reuse a separately admitted callback; no alternate
chemistry rules or success thresholds are introduced here.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import heapq
import json
import math
from numbers import Real

import torch


MAPPING_COUNT = 4
METRIC_ID = "receptor_aligned_graph_symmetry_heavy_rmsd/1.0.0"
CONTACT_RATIO_BINS = (0.8, 0.85, 0.9)
PLANARITY_DIAGNOSTIC_ANGSTROM = 0.1


class MetricDataError(ValueError):
    """A missing or malformed metric dependency cannot produce a valid label."""


def _digest(value, name):
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise MetricDataError(f"{name}: lowercase SHA-256 required")
    return value


def _json(value, name):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise MetricDataError(f"{name}: finite JSON data required") from error


def _source_facts(value):
    if not isinstance(value, Mapping) or not value:
        raise MetricDataError("nonempty source_facts with source digests required")
    facts = dict(value)
    digests = [v for k, v in facts.items() if isinstance(k, str) and k.endswith("sha256")]
    if not digests:
        raise MetricDataError("source_facts must include a top-level source SHA-256")
    for digest in digests:
        _digest(digest, "source_facts digest")
    return _json(facts, "source_facts")


def _finite_real(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def _coordinates(value, name, count=None):
    if isinstance(value, torch.Tensor):
        if value.dtype != torch.float64 or value.device.type != "cpu":
            raise MetricDataError(f"{name}: CPU float64 coordinates required")
        result = value.detach().clone()
    else:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise MetricDataError(f"{name}: finite Nx3 coordinates required")
        rows = []
        for row in value:
            if (not isinstance(row, Sequence) or isinstance(row, (str, bytes))
                    or len(row) != 3
                    or any(not _finite_real(v) for v in row)):
                raise MetricDataError(f"{name}: finite real Nx3 coordinates required")
            rows.append(tuple(float(v) for v in row))
        result = torch.tensor(rows, dtype=torch.float64)
    if (result.ndim != 2 or result.shape[1] != 3 or result.shape[0] == 0
            or (count is not None and result.shape[0] != count)
            or not bool(torch.isfinite(result).all())):
        raise MetricDataError(f"{name}: finite Nx3 coordinates with exact coverage required")
    return result


def _rows(value):
    return tuple(tuple(float(v) for v in row) for row in value.tolist())


def _rmsd(left, right):
    result = float(torch.sqrt(torch.mean(torch.sum((left - right) ** 2, dim=1))))
    if not math.isfinite(result):
        raise MetricDataError("coordinate differences exceed finite metric range")
    return result


@dataclass(frozen=True)
class ReceptorTransform:
    """Immutable row-vector transform: prepared = crystal @ rotation + translation."""

    rotation: tuple
    translation: tuple
    receptor_ca_count: int
    receptor_rmsd_angstrom: float
    determinant: float

    def apply(self, coordinates):
        points = _coordinates(coordinates, "coordinates to transform")
        with torch.no_grad():
            result = points @ torch.tensor(self.rotation, dtype=torch.float64)
            result += torch.tensor(self.translation, dtype=torch.float64)
        return _coordinates(result, "transformed coordinates")

    def document(self):
        return {
            "direction": "crystal_receptor_CA_to_prepared_receptor_CA",
            "row_vector_equation": "prepared = crystal @ rotation + translation",
            "rotation": [list(row) for row in self.rotation],
            "translation_angstrom": list(self.translation),
            "proper_rotation_determinant": self.determinant,
            "matched_receptor_CA_count": self.receptor_ca_count,
            "receptor_CA_rmsd_angstrom": self.receptor_rmsd_angstrom,
            "outlier_removal_performed": False,
            "ligand_used_in_fit": False,
        }


@torch.no_grad()
def fit_receptor_frame(crystal_ca, prepared_ca):
    """Fit all admitted CA pairs with proper Kabsch, without residual selection."""
    source = _coordinates(crystal_ca, "crystal receptor CA")
    target = _coordinates(prepared_ca, "prepared receptor CA", len(source))
    if len(source) < 3:
        raise MetricDataError("at least three noncollinear receptor CA pairs required")
    source_center, target_center = source.mean(0), target.mean(0)
    left, right = source - source_center, target - target_center
    covariance = left.T @ right
    if not bool(torch.isfinite(covariance).all()):
        raise MetricDataError("receptor covariance exceeds finite metric range")
    try:
        # Rank here is floating-point identifiability, not a scientific cutoff.
        if int(torch.linalg.matrix_rank(covariance)) < 2:
            raise MetricDataError("receptor correspondence does not determine a rigid frame")
        u, _singular, vh = torch.linalg.svd(covariance)
    except RuntimeError as error:
        raise MetricDataError("receptor frame decomposition failed") from error
    correction = torch.eye(3, dtype=torch.float64)
    correction[2, 2] = -1.0 if float(torch.linalg.det(u @ vh)) < 0 else 1.0
    rotation = u @ correction @ vh
    translation = target_center - source_center @ rotation
    determinant = float(torch.linalg.det(rotation))
    if not math.isfinite(determinant) or determinant <= 0:
        raise MetricDataError("proper receptor rotation could not be established")
    fitted = source @ rotation + translation
    return ReceptorTransform(_rows(rotation), tuple(float(v) for v in translation),
                             len(source), _rmsd(fitted, target), determinant)


def _maps(value, heavy_count):
    if (not isinstance(value, Sequence) or isinstance(value, (str, bytes))
            or len(value) != MAPPING_COUNT):
        raise MetricDataError("exactly four graph-admitted atom mappings required")
    result = []
    for row in value:
        if (not isinstance(row, Sequence) or isinstance(row, (str, bytes))
                or len(row) != heavy_count or any(type(i) is not int for i in row)
                or set(row) != set(range(heavy_count))):
            raise MetricDataError("each atom mapping must be a complete integer bijection")
        result.append(tuple(row))
    if len(set(result)) != MAPPING_COUNT:
        raise MetricDataError("duplicate graph-admitted mappings are invalid")
    return tuple(result)


@dataclass(frozen=True)
class ReceptorAlignedReference:
    transform: ReceptorTransform
    prepared_atom_count: int
    prepared_heavy_indices: tuple
    prepared_to_ccd_mappings: tuple
    reference_heavy_ccd_order: tuple
    source_facts_json: str
    metric_policy_sha256: str

    @torch.no_grad()
    def evaluate_states(self, states):
        """Label P0, raw start and an available final in one receptor frame.

        All four supplied graph mappings are retained. The minimum is symmetry
        normalization of one state, never selection among poses or model arms.
        """
        if (not isinstance(states, Mapping) or not {"P0", "start"} <= set(states)
                or any(not isinstance(k, str) or not k for k in states)):
            raise MetricDataError("P0 and start coordinate states are required")
        reference = torch.tensor(self.reference_heavy_ccd_order, dtype=torch.float64)
        selected = {
            name: _coordinates(value, name, self.prepared_atom_count)[
                list(self.prepared_heavy_indices)
            ] for name, value in states.items()
        }
        results = {}
        for name, points in selected.items():
            values = [_rmsd(points, reference[list(mapping)])
                      for mapping in self.prepared_to_ccd_mappings]
            results[name] = {
                "all_graph_mapping_rmsd_angstrom": values,
                "symmetry_aware_heavy_rmsd_angstrom": min(values),
                "minimum_mapping_index": values.index(min(values)),
                "direct_heavy_displacement_from_P0_rmsd_angstrom": _rmsd(points, selected["P0"]),
                "direct_heavy_displacement_from_start_rmsd_angstrom": _rmsd(points, selected["start"]),
                "ligand_fit_performed": False,
            }
        def rmsd(key):
            return results[key]["symmetry_aware_heavy_rmsd_angstrom"]

        return {
            "schema_version": "pfk_paired_pose_labels/1.0.0",
            "metric_id": METRIC_ID,
            "metric_policy_sha256": self.metric_policy_sha256,
            "source_facts": json.loads(self.source_facts_json),
            "source_facts_digest_sha256": hashlib.sha256(self.source_facts_json.encode()).hexdigest(),
            "receptor_alignment": self.transform.document(),
            "prepared_atom_count": self.prepared_atom_count,
            "prepared_heavy_indices": list(self.prepared_heavy_indices),
            "prepared_to_ccd_heavy_index_arrays": [list(row) for row in self.prepared_to_ccd_mappings],
            "states": results,
            "final_state_status": "measured" if "final" in results else "unavailable_not_supplied",
            "comparison": {
                "final_minus_P0_reference_rmsd_angstrom": rmsd("final") - rmsd("P0"),
                "final_minus_start_reference_rmsd_angstrom": rmsd("final") - rmsd("start"),
            } if "final" in results else None,
            "boundary": {
                "reference_is_evaluation_label_only": True,
                "reference_used_in_objective": False,
                "pose_selection_admitted": False,
                "chemical_validity": None,
                "scientific_qualification_admitted": False,
                "success_threshold_applied": False,
            },
        }


def admit_crystal_reference(crystal_ca, prepared_ca, crystal_heavy_ccd_order,
                            prepared_heavy_indices, prepared_to_ccd_mappings, *,
                            prepared_atom_count, source_facts, metric_policy_sha256):
    """Freeze an admitted source/map set and its single receptor-only transform."""
    if type(prepared_atom_count) is not int or prepared_atom_count < 1:
        raise MetricDataError("positive prepared atom count required")
    reference = _coordinates(crystal_heavy_ccd_order, "crystal ligand heavy atoms")
    if (not isinstance(prepared_heavy_indices, Sequence)
            or isinstance(prepared_heavy_indices, (str, bytes))
            or len(prepared_heavy_indices) != len(reference)
            or any(type(i) is not int or i < 0 or i >= prepared_atom_count
                   for i in prepared_heavy_indices)
            or len(set(prepared_heavy_indices)) != len(reference)):
        raise MetricDataError("unique complete prepared heavy-atom indices required")
    mappings = _maps(prepared_to_ccd_mappings, len(reference))
    facts = _source_facts(source_facts)
    policy = _digest(metric_policy_sha256, "metric policy")
    transform = fit_receptor_frame(crystal_ca, prepared_ca)
    return ReceptorAlignedReference(
        transform, prepared_atom_count, tuple(prepared_heavy_indices), mappings,
        _rows(transform.apply(reference)), facts, policy,
    )


def evaluate_structural_diagnostics(states, callback, *, criteria_sha256,
                                    implementation_sha256):
    """Reuse the caller's frozen original geometry/contact policy on copies.

    The callback takes ``(state_name, coordinates)`` and returns finite JSON.
    Its source and criteria are admitted by the caller; this wrapper neither
    substitutes chemistry rules nor treats its output as chemical validity.
    """
    criteria = _digest(criteria_sha256, "diagnostic criteria")
    implementation = _digest(implementation_sha256, "diagnostic implementation")
    if not callable(callback) or not isinstance(states, Mapping) or not states:
        raise MetricDataError("states and a source-admitted diagnostic callback required")
    prepared = {}
    atom_count = None
    for name, coordinates in states.items():
        if not isinstance(name, str) or not name:
            raise MetricDataError("nonempty diagnostic state names required")
        prepared[name] = _coordinates(coordinates, name, atom_count)
        atom_count = len(prepared[name])
    observed = {}
    for name, points in prepared.items():
        value = callback(name, points.clone())
        if not isinstance(value, Mapping) or not value:
            raise MetricDataError(f"{name}: nonempty diagnostic document required")
        observed[name] = json.loads(_json(dict(value), name))
    return {
        "schema_version": "pfk_source_bound_structural_diagnostics/1.0.0",
        "criteria_sha256": criteria,
        "implementation_sha256": implementation,
        "states": observed,
        "boundary": {
            "diagnostic_only": True,
            "full_PoseBusters": False,
            "chemical_validity": None,
            "reference_used_in_objective": False,
            "new_success_thresholds_added": False,
        },
    }


@torch.no_grad()
def ring_planarity(coordinates, admitted_ring_groups, *, source_sha256, policy_sha256):
    """Measure frozen original-policy groups; never discover groups from a pose.

    Group admission owns the original sanitized-SDF aromatic 5/6-ring policy.
    This numeric helper also accepts small synthetic groups for contract tests.
    The source policy's 0.1 angstrom bin is a diagnostic, not chemical validity.
    """
    source = _digest(source_sha256, "ring group source")
    policy = _digest(policy_sha256, "ring policy")
    points = _coordinates(coordinates, "ring coordinates")
    if len(points) > 256:
        raise MetricDataError("ring coordinate budget exceeded")
    if (not isinstance(admitted_ring_groups, Sequence)
            or isinstance(admitted_ring_groups, (str, bytes))
            or len(admitted_ring_groups) > 256):
        raise MetricDataError("bounded admitted ring groups required")
    groups, seen = [], set()
    for indices in admitted_ring_groups:
        if (not isinstance(indices, Sequence) or isinstance(indices, (str, bytes))
                or not 3 <= len(indices) <= len(points)
                or any(type(i) is not int or not 0 <= i < len(points) for i in indices)
                or len(set(indices)) != len(indices)):
            raise MetricDataError("unique valid ring atom indices required")
        key = tuple(sorted(indices))
        if key in seen:
            raise MetricDataError("duplicate admitted ring group")
        seen.add(key)
        groups.append(tuple(indices))
    rows = []
    for indices in groups:
        centered = points[list(indices)] - points[list(indices)].mean(0)
        if not bool(torch.isfinite(centered).all()):
            raise MetricDataError("ring coordinates exceed finite metric range")
        try:
            if int(torch.linalg.matrix_rank(centered)) < 2:
                raise MetricDataError("degenerate ring does not determine a plane")
            _u, singular, vh = torch.linalg.svd(centered, full_matrices=False)
        except RuntimeError as error:
            raise MetricDataError("ring plane decomposition failed") from error
        distances = torch.abs(centered @ vh[-1])
        maximum = float(distances.max())
        rms = float(torch.sqrt(torch.mean(distances ** 2)))
        if not math.isfinite(maximum) or not math.isfinite(rms):
            raise MetricDataError("ring planarity exceeds finite metric range")
        rows.append({
            "atom_indices": list(indices),
            "maximum_plane_distance_angstrom": maximum,
            "rms_plane_distance_angstrom": rms,
            "singular_values_angstrom": [float(v) for v in singular],
            "above_source_diagnostic_threshold": maximum > PLANARITY_DIAGNOSTIC_ANGSTROM,
        })
    return {
        "schema_version": "pfk_admitted_ring_planarity_diagnostics/1.0.0",
        "source_sha256": source,
        "policy_sha256": policy,
        "status": "measured" if groups else "not_applicable_no_admitted_groups",
        "source_diagnostic_threshold_angstrom": PLANARITY_DIAGNOSTIC_ANGSTROM,
        "group_count": len(rows),
        "groups": rows,
        "groups_above_source_diagnostic_threshold": sum(
            row["above_source_diagnostic_threshold"] for row in rows),
        "boundary": {"diagnostic_only": True, "chemical_validity": None,
                     "full_PoseBusters": False, "groups_selected_using_pose": False},
    }


def _radii(value, count, name):
    if isinstance(value, torch.Tensor):
        if value.dtype != torch.float64 or value.device.type != "cpu":
            raise MetricDataError(f"{name}: CPU float64 radii required")
        result = value.detach().clone()
    else:
        if (not isinstance(value, Sequence) or isinstance(value, (str, bytes))
                or any(not _finite_real(v) for v in value)):
            raise MetricDataError(f"{name}: finite positive radii required")
        result = torch.tensor(value, dtype=torch.float64)
    if (tuple(result.shape) != (count,) or not bool(torch.isfinite(result).all())
            or not bool((result > 0).all())):
        raise MetricDataError(f"{name}: exact coverage with positive finite radii required")
    return result


@torch.no_grad()
def closest_contacts(ligand_heavy_coordinates, receptor_heavy_coordinates,
                     admitted_element_vdw_radii, ratio_threshold=0.85, *,
                     source_sha256, policy_sha256, max_contact_rows=100):
    """Count every heavy pair before retaining bounded nearest-contact rows.

    Radii are caller-admitted RDKit element vdW radii in angstrom, in the exact
    respective heavy-array orders. They are not Lennard-Jones sigma parameters.
    The original 0.8/0.85/0.9 bins are diagnostics; signed overlap is not clipped.
    """
    source = _digest(source_sha256, "vdW radius source")
    policy = _digest(policy_sha256, "contact policy")
    ligand = _coordinates(ligand_heavy_coordinates, "ligand heavy coordinates")
    receptor = _coordinates(receptor_heavy_coordinates, "receptor heavy coordinates")
    if len(ligand) > 256 or len(receptor) > 8192:
        raise MetricDataError("contact coordinate budget exceeded")
    if (not isinstance(admitted_element_vdw_radii, Mapping)
            or set(admitted_element_vdw_radii) != {"ligand", "receptor"}):
        raise MetricDataError("separate admitted ligand and receptor element radii required")
    if not _finite_real(ratio_threshold) or ratio_threshold not in CONTACT_RATIO_BINS:
        raise MetricDataError("contact ratio must be an original-policy diagnostic bin")
    if type(max_contact_rows) is not int or not 0 <= max_contact_rows <= 4096:
        raise MetricDataError("contact row budget must be an integer in 0..4096")
    ligand_radii = _radii(admitted_element_vdw_radii["ligand"], len(ligand), "ligand radii")
    receptor_radii = _radii(admitted_element_vdw_radii["receptor"], len(receptor), "receptor radii")
    counts = {str(t): 0 for t in CONTACT_RATIO_BINS}
    nearest, heap = None, []
    for li in range(0, len(ligand), 128):
        for ri in range(0, len(receptor), 256):
            a, b = ligand[li:li+128], receptor[ri:ri+256]
            distances = torch.linalg.vector_norm(a[:, None] - b[None, :], dim=-1)
            sums = ligand_radii[li:li+128, None] + receptor_radii[None, ri:ri+256]
            if not bool(torch.isfinite(distances).all()) or not bool(torch.isfinite(sums).all()):
                raise MetricDataError("contact arithmetic exceeds finite metric range")
            ratios = distances / sums
            if not bool(torch.isfinite(ratios).all()):
                raise MetricDataError("contact ratios exceed finite metric range")
            for threshold in CONTACT_RATIO_BINS:
                counts[str(threshold)] += int((ratios < threshold).sum())

            def row(flat_index):
                i, j = divmod(flat_index, len(b))
                return {
                    "ligand_heavy_order_index": li + i,
                    "receptor_heavy_order_index": ri + j,
                    "distance_angstrom": float(distances[i, j]),
                    "vdw_radius_sum_angstrom": float(sums[i, j]),
                    "vdw_ratio": float(ratios[i, j]),
                    "signed_overlap_angstrom": float(sums[i, j] - distances[i, j]),
                }

            minimum = row(int(torch.argmin(ratios.reshape(-1))))
            def key(z):
                return (z["vdw_ratio"], z["ligand_heavy_order_index"], z["receptor_heavy_order_index"])

            if nearest is None or key(minimum) < key(nearest):
                nearest = minimum
            # Per-block top K contains every possible global top K. Stable sort
            # plus index tie-breaking prevents selection from changing counts.
            if max_contact_rows:
                order = torch.argsort(ratios.reshape(-1), stable=True)[:max_contact_rows]
                for flat_index in order.tolist():
                    contact = row(flat_index)
                    if contact["vdw_ratio"] >= CONTACT_RATIO_BINS[-1]:
                        break
                    score = key(contact)
                    item = (-score[0], -score[1], -score[2], contact)
                    if len(heap) < max_contact_rows:
                        heapq.heappush(heap, item)
                    elif item[:3] > heap[0][:3]:
                        heapq.heapreplace(heap, item)
    rows = sorted((item[3] for item in heap), key=lambda z: (
        z["vdw_ratio"], z["ligand_heavy_order_index"], z["receptor_heavy_order_index"]))
    return {
        "schema_version": "pfk_source_element_vdw_contact_diagnostics/1.0.0",
        "source_sha256": source,
        "policy_sha256": policy,
        "ligand_heavy_atom_count": len(ligand),
        "receptor_heavy_atom_count": len(receptor),
        "all_pair_denominator": len(ligand) * len(receptor),
        "all_pair_counts_below_ratio": counts,
        "selected_source_diagnostic_ratio": ratio_threshold,
        "all_pairs_below_selected_ratio": counts[str(ratio_threshold)],
        "minimum_vdw_ratio": nearest["vdw_ratio"],
        "closest_pair": nearest,
        "nearby_contact_rows_below_ratio": CONTACT_RATIO_BINS[-1],
        "nearby_contact_rows": rows,
        "max_contact_rows": max_contact_rows,
        "nearby_contact_rows_truncated": counts["0.9"] > len(rows),
        "pair_counts_are_complete": True,
        "boundary": {"diagnostic_only": True, "chemical_validity": None,
                     "full_PoseBusters": False, "radii_are_LJ_sigma": False},
    }
