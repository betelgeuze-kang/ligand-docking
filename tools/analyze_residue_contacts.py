#!/usr/bin/env python3
"""Bounded, stdlib-only geometric residue contacts; not chemical interactions."""
import argparse
import bisect
import hashlib
import json
import math
import sys

SCHEMA = "residue_contacts_input.v1"
LIMITS = {
    "input_bytes": 2_000_000, "residues": 10_000, "receptor_atoms": 50_000,
    "poses": 1_000, "ligand_atoms": 50_000, "comparison_pairs": 5_000,
    "distance_ops": 5_000_000, "output_rows": 100_000,
    "output_bytes": 8_000_000,
}


class ContactInputError(ValueError):
    """Safe, fixed diagnostic; never includes input values or file paths."""


def _fail(code):
    raise ContactInputError(code)


def _object(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        _fail("invalid_object_fields")


def _text(value, empty=False):
    if not isinstance(value, str) or len(value) > 128 or (not value and not empty):
        _fail("invalid_identifier_or_label")
    if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        _fail("invalid_identifier_or_label")
    return value


def _number(value):
    if type(value) not in (int, float) or not -1e150 <= value <= 1e150:
        _fail("invalid_or_out_of_range_number")
    return float(value)


def _list(value, maximum):
    if not isinstance(value, list):
        _fail("expected_array")
    if len(value) > maximum:
        _fail("count_budget_exceeded")
    return value


def _unique(items, key):
    seen = set()
    for item in items:
        ident = _text(item[key])
        if ident in seen:
            _fail("duplicate_identifier")
        seen.add(ident)
    return seen


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_json_key")
        result[key] = value
    return result


def _constant(_):
    _fail("nonfinite_json_number")


def _geometry(container, maximum, residue_ids=None):
    if "atoms" not in container:
        return "missing", None
    if container["atoms"] is None:
        return "null", None
    atoms = _list(container["atoms"], maximum)
    for atom in atoms:
        required = ("atom_id", "element", "xyz")
        if residue_ids is not None:
            required += ("residue_id",)
        _object(atom, required)
        _text(atom["element"])
        xyz = _list(atom["xyz"], 3)
        if len(xyz) != 3:
            _fail("invalid_xyz")
        for v in xyz:
            _number(v)
        if residue_ids is not None:
            if _text(atom["residue_id"]) not in residue_ids:
                _fail("unknown_residue_reference")
    _unique(atoms, "atom_id")
    return ("observed" if atoms else "empty"), atoms


def _limits(overrides):
    result = dict(LIMITS)
    if overrides is not None:
        _object(overrides, (), LIMITS)
        for key, value in overrides.items():
            if type(value) is not int or value < 0 or value > LIMITS[key]:
                _fail("invalid_budget_override")
            result[key] = value
    return result


def analyze_contacts(raw, *, limits=None):
    """Analyze UTF-8 JSON bytes without mutation, imports, or external I/O.

    Budget overrides may only lower hard limits. Hash binds exact bytes, not their
    authenticity. Poses must explicitly include unavailable expected pose IDs.
    """
    budget = _limits(limits)
    if not isinstance(raw, bytes):
        _fail("expected_bytes")
    if len(raw) > budget["input_bytes"]:
        _fail("input_byte_budget_exceeded")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ContactInputError):
            raise
        raise ContactInputError("invalid_json") from None
    _object(data, ("schema_version", "coordinate_frame", "units", "receptor", "poses", "comparisons"), ("settings",))
    if data["schema_version"] != SCHEMA:
        _fail("unsupported_schema")
    frame = _text(data["coordinate_frame"])
    if data["units"] != "angstrom":
        _fail("unsupported_units")
    settings = data.get("settings", {})
    _object(settings, (), ("cutoff", "bin_edges"))
    cutoff = _number(settings.get("cutoff", 8.0))
    edges = [_number(v) for v in _list(settings.get("bin_edges", [2.0, 4.0, 8.0]), 32)]
    if cutoff < 0 or not edges or edges[0] < 0 or any(a >= b for a, b in zip(edges, edges[1:])):
        _fail("invalid_cutoff_or_bins")
    receptor = data["receptor"]
    _object(receptor, ("residues",), ("atoms",))
    residues = _list(receptor["residues"], budget["residues"])
    for residue in residues:
        _object(residue, ("residue_id",), ("chain", "resnum", "icode", "name"))
        for key in ("chain", "resnum", "icode", "name"):
            if key in residue and residue[key] is not None:
                _text(residue[key], empty=True)
    residue_ids = _unique(residues, "residue_id")
    receptor_state, receptor_atoms = _geometry(receptor, budget["receptor_atoms"], residue_ids)
    poses = _list(data["poses"], budget["poses"])
    geometries = {}
    ligand_count = 0
    for pose in poses:
        _object(pose, ("pose_id", "coordinate_frame"), ("atoms",))
        _text(pose["pose_id"])
        if _text(pose["coordinate_frame"]) != frame:
            _fail("incompatible_coordinate_frame")
        state, atoms = _geometry(pose, budget["ligand_atoms"])
        geometries[pose["pose_id"]] = (state, atoms)
        ligand_count += len(atoms or [])
    pose_ids = _unique(poses, "pose_id")
    comparisons = _list(data["comparisons"], budget["comparison_pairs"])
    for pair in comparisons:
        _object(pair, ("comparison_id", "initial_pose_id", "final_pose_id"))
        for key in ("initial_pose_id", "final_pose_id"):
            if _text(pair[key]) not in pose_ids:
                _fail("unknown_pose_reference")
    _unique(comparisons, "comparison_id")
    operations = len(receptor_atoms or []) * ligand_count
    # Include worst-case per-comparison residue lists, not only nearest rows.
    rows = len(residues) * (len(poses) + 3 * len(comparisons)) + len(poses) + len(comparisons)
    if ligand_count > budget["ligand_atoms"] or operations > budget["distance_ops"] or rows > budget["output_rows"]:
        _fail("work_budget_exceeded")
    # No pairwise distance matrix: retain one minimum per residue and pose.
    grouped = {rid: [] for rid in residue_ids}
    for atom in receptor_atoms or []:
        grouped[atom["residue_id"]].append(atom)
    pose_results = []
    contacts = {}
    for pose in sorted(poses, key=lambda p: p["pose_id"]):
        pid = pose["pose_id"]
        state, atoms = geometries[pid]
        geometry_present = receptor_atoms is not None and atoms is not None
        available = bool(receptor_atoms) and bool(atoms) and all(grouped.values())
        contact_set = set() if available else None
        nearest = []
        for rid in sorted(residue_ids):
            best = None
            reason = None
            if not geometry_present:
                reason = "unavailable_geometry"
            elif not atoms:
                reason = "empty_ligand_atoms"
            elif not grouped[rid]:
                reason = "empty_residue_atoms"
            else:
                for ra in grouped[rid]:
                    for la in atoms:
                        distance = math.dist(ra["xyz"], la["xyz"])
                        if not math.isfinite(distance):
                            _fail("distance_overflow")
                        candidate = (distance, ra["atom_id"], la["atom_id"])
                        if best is None or candidate < best:
                            best = candidate
            hit = best[0] <= cutoff if best is not None else None
            if hit and contact_set is not None:
                contact_set.add(rid)
            nearest.append({"residue_id": rid, "distance": best[0] if best else None,
                            "receptor_atom_id": best[1] if best else None,
                            "ligand_atom_id": best[2] if best else None,
                            "bin_index": bisect.bisect_left(edges, best[0]) if best else None,
                            "contact": hit, "reason": reason})
        contacts[pid] = contact_set
        pose_results.append({"pose_id": pid, "geometry_state": state,
                             "fingerprint_state": "complete" if available else "unavailable",
                             "contact_residue_ids": sorted(contact_set) if available else None,
                             "contact_count": len(contact_set) if available else None,
                             "nearest_by_residue": nearest})
    pair_results = []
    for pair in sorted(comparisons, key=lambda p: p["comparison_id"]):
        first, last = contacts[pair["initial_pose_id"]], contacts[pair["final_pose_id"]]
        available = first is not None and last is not None
        union = first | last if available else None
        jaccard = len(first & last) / len(union) if union else None
        pair_results.append({**pair, "gained_residue_ids": sorted(last - first) if available else None,
                             "lost_residue_ids": sorted(first - last) if available else None,
                             "shared_residue_ids": sorted(first & last) if available else None,
                             "jaccard": jaccard, "jaccard_distance": 1 - jaccard if jaccard is not None else None,
                             "reason": "unavailable_geometry" if not available else ("empty_contact_union" if not union else None)})
    observed = [tuple(sorted(s)) for s in contacts.values() if s is not None]
    output = {
        "schema_version": "residue_contacts_output.v1", "input_sha256": hashlib.sha256(raw).hexdigest(),
        "input_bytes": len(raw), "coordinate_frame": frame, "units": "angstrom",
        "settings": {"cutoff": cutoff, "bin_edges": edges, "bin_rule": "[0,e0],(e0,e1],...,(last,infinity)",
                     "all_supplied_atoms": True, "periodic": False, "alignment": False},
        "limits": budget, "preflight": {"distance_ops": operations, "output_row_upper_bound": rows},
        "receptor_geometry_state": receptor_state,
        "residues": sorted(residues, key=lambda r: r["residue_id"]),
        "poses": pose_results, "comparisons": pair_results,
        "contact_set_diversity": {"supplied_pose_count": len(poses), "available_pose_count": len(observed),
                                  "unavailable_pose_count": len(poses) - len(observed),
                                  "distinct_available_contact_sets": len(set(observed)) if observed else None},
        "claims": {key: False for key in ("chemical_interactions", "affinity_accuracy", "scientific_validation",
                                         "benchmark_promotion", "gpu_validation", "product_readiness",
                                         "customer_readiness", "commercial_readiness", "authenticated_evidence")},
    }
    # Validate serialized size for callable users as well as CLI; no partial stdout.
    _serialize(output, budget["output_bytes"])
    return output


def _serialize(output, maximum):
    text = json.dumps(output, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n"
    if len(text.encode("ascii")) > maximum:
        _fail("output_byte_budget_exceeded")
    return text


def render_text(output):
    """Human-readable complete report; JSON-escape labels to avoid terminal injection."""
    lines = ["Geometric residue contacts only; no chemical/affinity claims.",
             "Input SHA-256 (bytes only): " + output["input_sha256"],
             "Settings: " + json.dumps(output["settings"], sort_keys=True),
             "Receptor geometry: " + output["receptor_geometry_state"]]
    for pose in output["poses"]:
        lines.append("Pose " + json.dumps(pose["pose_id"]) + ": " + pose["geometry_state"]
                     + "; fingerprint=" + pose["fingerprint_state"]
                     + "; contact_count=" + json.dumps(pose["contact_count"]))
        lines.extend(json.dumps(row, sort_keys=True) for row in pose["nearest_by_residue"])
    lines.extend("Comparison: " + json.dumps(pair, sort_keys=True) for pair in output["comparisons"])
    lines.append("Diversity: " + json.dumps(output["contact_set_diversity"], sort_keys=True))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="UTF-8 v1 JSON input path; no file is modified")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)
    try:
        with open(args.input, "rb") as source:
            raw = source.read(LIMITS["input_bytes"] + 1)
        output = analyze_contacts(raw)
        rendered = _serialize(output, LIMITS["output_bytes"]) if args.format == "json" else render_text(output)
        if len(rendered.encode("utf-8")) > LIMITS["output_bytes"]:
            _fail("output_byte_budget_exceeded")
    except ContactInputError as exc:
        print("residue_contacts: " + str(exc), file=sys.stderr)
        return 2
    except OSError:
        print("residue_contacts: input_read_failed", file=sys.stderr)
        return 2
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
