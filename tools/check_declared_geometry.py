#!/usr/bin/env python3
"""Evaluate explicit angle/plane-RMS policies; not a chemical validity certificate."""
import argparse
import hashlib
import json
import math
import sys

SCHEMA = "betelgeuze.declared_geometry/1"
MAX_BYTES = 1048576
MAX_ATOMS = 10000
MAX_CHECKS = 2000
MAX_GROUP = 32
MAX_COORD = 1e6
ANGLE_GUARD_DEG = 1e-10
RANK_RELATIVE_GUARD = 1e-12
EIGEN_GUARD = 128 * sys.float_info.epsilon


class InputError(ValueError):
    """Malformed or unsupported input, not a failed molecular constraint."""


def _keys(obj, allowed, required, where):
    if not isinstance(obj, dict) or set(obj) - set(allowed) or set(required) - set(obj):
        raise InputError("invalid fields: " + where)


def _string(value, where):
    if not isinstance(value, str) or not value or len(value) > 256 or any(ord(c) < 32 for c in value):
        raise InputError("invalid string: " + where)
    return value


def _number(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError("invalid number: " + where)
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise InputError("out-of-range number: " + where) from None
    if not math.isfinite(result):
        raise InputError("non-finite number: " + where)
    return result


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate JSON key")
        result[key] = value
    return result


def parse_bytes(data):
    if len(data) > MAX_BYTES:
        raise InputError("input byte budget exceeded")
    try:
        obj = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(InputError("non-finite JSON")))
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise InputError("invalid JSON: " + type(exc).__name__) from None
    stack = [(obj, 0)]
    while stack:
        value, depth = stack.pop()
        if depth > 24:
            raise InputError("JSON depth budget exceeded")
        if isinstance(value, dict):
            stack.extend((v, depth + 1) for v in value.values())
        elif isinstance(value, list):
            stack.extend((v, depth + 1) for v in value)
    return obj


def _policy(value):
    if value is None:
        return None
    _keys(value, ("id", "version", "source"), ("id", "version", "source"), "policy")
    return {key: _string(value[key], "policy." + key) for key in ("id", "version", "source")}


def _validate(obj):
    _keys(obj, ("schema", "units", "frame_id", "state_id", "atoms", "expected_checks"),
          ("schema", "units", "frame_id", "state_id", "atoms", "expected_checks"), "root")
    if obj["schema"] != SCHEMA or obj["units"] != {"coordinates": "angstrom", "angles": "degree"}:
        raise InputError("unsupported schema or units")
    for key in ("frame_id", "state_id"):
        _string(obj[key], key)
    atoms = obj["atoms"]
    checks = obj["expected_checks"]
    if not isinstance(atoms, list) or len(atoms) > MAX_ATOMS:
        raise InputError("atom budget/type")
    if not isinstance(checks, list) or len(checks) > MAX_CHECKS:
        raise InputError("check budget/type")
    coords = {}
    for atom in atoms:
        _keys(atom, ("id", "xyz"), ("id", "xyz"), "atom")
        atom_id = _string(atom["id"], "atom.id")
        if atom_id in coords:
            raise InputError("duplicate atom id")
        xyz = atom["xyz"]
        if not isinstance(xyz, list) or len(xyz) != 3:
            raise InputError("invalid xyz")
        xyz = tuple(_number(v, "xyz") for v in xyz)
        if any(abs(v) > MAX_COORD for v in xyz):
            raise InputError("coordinate domain exceeded")
        coords[atom_id] = xyz
    seen = set()
    normalized = []
    for check in checks:
        _keys(check, ("id", "kind", "atoms", "policy", "bounds", "max_rms_angstrom"),
              ("id", "kind", "atoms"), "check")
        cid = _string(check["id"], "check.id")
        if cid in seen:
            raise InputError("duplicate check id")
        seen.add(cid)
        kind = check["kind"]
        if kind not in ("angle", "plane_rms"):
            raise InputError("unsupported check kind")
        ids = check["atoms"]
        if not isinstance(ids, list) or not (3 <= len(ids) <= MAX_GROUP):
            raise InputError("invalid check atom count")
        ids = [_string(v, "check atom id") for v in ids]
        if len(set(ids)) != len(ids):
            raise InputError("duplicate atom in check")
        if (kind == "angle" and len(ids) != 3) or (kind == "plane_rms" and len(ids) < 4):
            raise InputError("invalid kind atom count")
        policy = _policy(check.get("policy"))
        bounds = None
        if kind == "angle":
            if "max_rms_angstrom" in check:
                raise InputError("wrong threshold for angle")
            raw = check.get("bounds")
            if raw is not None:
                if not isinstance(raw, list) or len(raw) != 2:
                    raise InputError("invalid angle bounds")
                bounds = [_number(v, "angle bound") for v in raw]
                if not 0 <= bounds[0] <= bounds[1] <= 180:
                    raise InputError("angle bounds outside [0,180]")
        else:
            if "bounds" in check:
                raise InputError("wrong threshold for plane")
            raw = check.get("max_rms_angstrom")
            if raw is not None:
                bounds = _number(raw, "plane RMS bound")
                if not 0 <= bounds <= 2 * MAX_COORD:
                    raise InputError("plane RMS bound outside domain")
        normalized.append((cid, kind, ids, policy, bounds))
    return coords, normalized


def _angle(points):
    left = [points[0][i] - points[1][i] for i in range(3)]
    right = [points[2][i] - points[1][i] for i in range(3)]
    ln, rn = math.hypot(*left), math.hypot(*right)
    if min(ln, rn) <= 1e-12:
        return None, "DEGENERATE_ANGLE"
    u, v = [a / ln for a in left], [a / rn for a in right]
    cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
    return math.degrees(math.atan2(math.hypot(*cross), math.fsum(a*b for a, b in zip(u, v)))), None


def _eigenvalues(matrix):
    """Bounded Jacobi diagonalization of a normalized symmetric 3x3 matrix."""
    a = [row[:] for row in matrix]
    for _ in range(64):
        p, q = max(((0, 1), (0, 2), (1, 2)), key=lambda ij: abs(a[ij[0]][ij[1]]))
        if abs(a[p][q]) <= 1e-15:
            return sorted(a[i][i] for i in range(3)), max(abs(a[i][j]) for i, j in ((0, 1), (0, 2), (1, 2)))
        theta = 0.5 * math.atan2(2 * a[p][q], a[q][q] - a[p][p])
        c, s = math.cos(theta), math.sin(theta)
        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        a[p][p] = c*c*app - 2*s*c*apq + s*s*aqq
        a[q][q] = s*s*app + 2*s*c*apq + c*c*aqq
        a[p][q] = a[q][p] = 0.0
        for k in range(3):
            if k not in (p, q):
                akp, akq = a[k][p], a[k][q]
                a[k][p] = a[p][k] = c*akp - s*akq
                a[k][q] = a[q][k] = s*akp + c*akq
    return None, None


def _plane(points):
    n = len(points)
    # Subtract an observed anchor before averaging, avoiding cancellation from
    # a large common translation when group dimensions are small.
    anchor = points[0]
    shifted = [[p[i] - anchor[i] for i in range(3)] for p in points]
    center = [math.fsum(p[i] for p in shifted) / n for i in range(3)]
    centered = [[p[i] - center[i] for i in range(3)] for p in shifted]
    scale = max(abs(v) for p in centered for v in p)
    if scale <= 1e-12:
        return None, "DEGENERATE_PLANAR_GROUP"
    scaled = [[v / scale for v in p] for p in centered]
    cov = [[math.fsum(p[i]*p[j] for p in scaled) / n for j in range(3)] for i in range(3)]
    eig, residual = _eigenvalues(cov)
    if eig is None or eig[0] < -EIGEN_GUARD or not all(math.isfinite(v) for v in eig):
        return None, "NUMERIC_UNRESOLVED"
    if eig[1] <= RANK_RELATIVE_GUARD * max(eig[2], EIGEN_GUARD):
        return None, "DEGENERATE_PLANAR_GROUP"
    minimum = max(0.0, eig[0])
    return {"rms_angstrom": scale * math.sqrt(minimum), "normalized_eigenvalues": eig,
            "coordinate_scale_angstrom": scale, "normalized_eigenvalue_guard": EIGEN_GUARD + 2*residual}, None


def evaluate(obj):
    coords, checks = _validate(obj)
    rows = []
    for cid, kind, ids, policy, bounds in checks:
        row = {"id": cid, "kind": kind, "atoms": ids, "policy": policy,
               "policy_provenance_verified": False, "status": "UNKNOWN", "reason": None,
               "measurement": None, "threshold": bounds}
        missing = [v for v in ids if v not in coords]
        if missing:
            row.update(reason="MISSING_COORDINATES", missing_atom_ids=missing)
        elif policy is None or bounds is None:
            row["reason"] = "MISSING_POLICY_OR_THRESHOLD"
        else:
            points = [coords[v] for v in ids]
            if kind == "angle":
                angle, reason = _angle(points)
                row["measurement"] = angle
                if reason:
                    row["reason"] = reason
                elif min(abs(angle-bounds[0]), abs(angle-bounds[1])) <= ANGLE_GUARD_DEG:
                    row["reason"] = "NUMERIC_BOUNDARY"
                else:
                    row["status"] = "SATISFIED" if bounds[0] <= angle <= bounds[1] else "VIOLATED"
            else:
                plane, reason = _plane(points)
                row["measurement"] = plane
                if reason:
                    row["reason"] = reason
                else:
                    observed = max(0.0, plane["normalized_eigenvalues"][0])
                    threshold_squared = (bounds / plane["coordinate_scale_angstrom"]) ** 2
                    if abs(observed-threshold_squared) <= plane["normalized_eigenvalue_guard"]:
                        row["reason"] = "NUMERIC_BOUNDARY"
                    else:
                        row["status"] = "SATISFIED" if observed <= threshold_squared else "VIOLATED"
        rows.append(row)
    counts = {"requested": len(rows)}
    counts.update({status.lower(): sum(row["status"] == status for row in rows)
                   for status in ("SATISFIED", "VIOLATED", "UNKNOWN")})
    complete = bool(rows) and counts["unknown"] == 0
    return {"schema": "betelgeuze.declared_geometry_report/1", "frame_id": obj["frame_id"],
            "state_id": obj["state_id"], "rows": rows, "counts": counts,
            "coverage_complete": complete,
            "all_declared_constraints_satisfied": complete and counts["violated"] == 0,
            "chemical_identity_verified": False, "whole_molecule_validity_assessed": False,
            "engine_admission": "NOT_ASSESSED", "metric": "best_fit_plane_rms_distance_angstrom",
            "numeric_policy": {"angle_boundary_guard_degree": ANGLE_GUARD_DEG,
                               "rank_relative_guard": RANK_RELATIVE_GUARD,
                               "normalized_eigenvalue_guard": EIGEN_GUARD,
                               "minimum_extent_angstrom": 1e-12,
                               "guards_are_certified_error_bounds": False}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON path or '-' for stdin; stdout only")
    args = parser.parse_args(argv)
    try:
        if args.input == "-":
            data = sys.stdin.buffer.read(MAX_BYTES + 1)
        else:
            with open(args.input, "rb") as stream:
                data = stream.read(MAX_BYTES + 1)
        result = evaluate(parse_bytes(data))
        result["input_sha256"] = hashlib.sha256(data).hexdigest()
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode("utf-8")) > 4 * MAX_BYTES:
            raise InputError("output byte budget exceeded")
        print(encoded)
        return 0  # Success means report emitted, never molecular validity.
    except (InputError, OSError) as exc:
        reason = "INPUT_IO_ERROR" if isinstance(exc, OSError) else str(exc)
        print(json.dumps({"status": "INPUT_ERROR", "reason": reason}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
