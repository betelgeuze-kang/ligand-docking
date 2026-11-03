#!/usr/bin/env python3
"""Offline, bounded multi-h consistency checks of supplied energy/force evidence.

No molecular evaluator is imported or executed. A consistency result is conditional
on supplied data and policy, not scientific/native-engine qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

SCHEMA = "saved_force_differences/1"
MAX_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_SAMPLES = 4096
MAX_COORDINATE_CHECKS = 2_000_000
CONTEXT_KEYS = {"model", "chemical_state", "frame", "frozen_environment", "engine"}
POLICY_KEYS = {"force_atol", "force_rtol", "stability_atol", "stability_rtol",
               "roundoff_fraction", "energy_resolution", "domain"}


class EvidenceError(ValueError):
    """Invalid evidence contract; messages deliberately omit supplied labels/paths."""


def _require(condition, message):
    if not condition:
        raise EvidenceError(message)


def _keys(value, required, optional=()):
    _require(isinstance(value, dict), "expected object")
    _require(set(value) >= set(required) and set(value) <= set(required) | set(optional),
             "unsupported or missing fields")


def _number(value, *, minimum=None, maximum=None):
    _require(type(value) in (int, float), "expected finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError):
        raise EvidenceError("number out of range") from None
    _require(math.isfinite(result), "expected finite number")
    _require(minimum is None or result >= minimum, "number below bound")
    _require(maximum is None or result <= maximum, "number above bound")
    return result


def _integer(value, low, high):
    _require(type(value) is int and low <= value <= high, "integer out of range")
    return value


def _label(value):
    _require(isinstance(value, str) and 1 <= len(value) <= 128 and
             all(32 <= ord(c) < 127 for c in value), "invalid identifier")
    return value


def _digest(value):
    _require(isinstance(value, str) and len(value) == 64 and
             all(c in "0123456789abcdef" for c in value), "invalid digest")
    return value


def canonical_sha256(value):
    """Digest of canonical ASCII JSON; does not authenticate a producer."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def geometry_sha256(coordinates):
    return canonical_sha256([[float(v).hex() for v in row] for row in coordinates])


def _coordinates(value, n):
    _require(isinstance(value, list) and len(value) == n, "coordinate shape mismatch")
    result = []
    for row in value:
        _require(isinstance(row, list) and len(row) == 3, "coordinate shape mismatch")
        result.append([_number(v) for v in row])
    return result


def _channels(value, terms, *, n=None):
    _require(isinstance(value, dict) and set(value) <= set(terms), "unexpected energy channel")
    return {term: (_number(item) if n is None else _coordinates(item, n))
            for term, item in value.items()}


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def load_bytes(raw):
    _require(isinstance(raw, bytes) and len(raw) <= MAX_BYTES, "input byte budget exceeded")
    # Limit nesting before JSON parsing (ignore brackets inside quoted strings).
    depth = 0
    quoted = escaped = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            _require(depth <= 32, "JSON nesting budget exceeded")
        elif byte in (93, 125):
            depth -= 1
    try:
        return json.loads(raw, object_pairs_hook=_unique_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(EvidenceError("nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, EvidenceError):
            raise
        raise EvidenceError("invalid JSON") from None


def _validate(data):
    _keys(data, {"schema", "units", "force_convention", "context", "context_sha256",
                 "atom_ids", "expected_terms", "steps", "policy", "baseline", "samples"})
    _require(data["schema"] == SCHEMA, "unsupported schema")
    _require(data["units"] == {"energy": "kcal/mol", "length": "angstrom",
                               "force": "kcal/mol/angstrom"}, "unsupported units")
    _require(data["force_convention"] == "minus_energy_gradient", "unsupported force convention")
    _keys(data["context"], CONTEXT_KEYS)
    for value in data["context"].values():
        _label(value)
    context_hash = _digest(data["context_sha256"])
    _require(context_hash == canonical_sha256(data["context"]), "context digest mismatch")
    atoms = data["atom_ids"]
    _require(isinstance(atoms, list) and 1 <= len(atoms) <= 128, "atom budget exceeded")
    for atom in atoms:
        _label(atom)
    _require(len(set(atoms)) == len(atoms), "duplicate atom identity")
    n = len(atoms)
    terms = data["expected_terms"]
    _require(isinstance(terms, list) and 1 <= len(terms) <= 8, "channel budget exceeded")
    for term in terms:
        _label(term)
    _require(len(set(terms)) == len(terms), "duplicate expected channel")
    steps = data["steps"]
    _require(isinstance(steps, list) and 3 <= len(steps) <= 6, "three to six steps required")
    steps = [_number(h, minimum=0) for h in steps]
    _require(all(h > 0 for h in steps) and all(a > b for a, b in zip(steps, steps[1:])),
             "steps must be positive and strictly decreasing")
    _require(6 * n * len(steps) <= MAX_SAMPLES, "sample budget exceeded")
    p = data["policy"]
    _keys(p, POLICY_KEYS)
    _require(p["domain"] in ("smooth", "unknown", "nonsmooth"), "unsupported domain")
    policy = {key: _number(p[key], minimum=0) for key in POLICY_KEYS - {"domain"}}
    policy["domain"] = p["domain"]
    _require(policy["force_rtol"] < 1 and policy["stability_rtol"] < 1, "relative tolerance must be below one")
    _require(0 < policy["roundoff_fraction"] <= 1, "invalid roundoff fraction")
    _require(policy["force_atol"] > 0 and policy["stability_atol"] > 0,
             "positive absolute tolerances required")
    b = data["baseline"]
    _keys(b, {"coordinates", "geometry_sha256", "energies", "forces"})
    coords = _coordinates(b["coordinates"], n)
    _require(_digest(b["geometry_sha256"]) == geometry_sha256(coords), "baseline geometry digest mismatch")
    energies = _channels(b["energies"], terms)
    forces = _channels(b["forces"], terms, n=n)
    samples = data["samples"]
    _require(isinstance(samples, list) and len(samples) <= MAX_SAMPLES, "sample budget exceeded")
    _require(len(samples) * n * 3 <= MAX_COORDINATE_CHECKS, "coordinate operation budget exceeded")
    indexed = {}
    for sample in samples:
        _keys(sample, {"atom_index", "axis", "h", "sign", "status", "context_sha256"},
              {"coordinates", "geometry_sha256", "energies"})
        i = _integer(sample["atom_index"], 0, n - 1)
        axis = _integer(sample["axis"], 0, 2)
        sign = _integer(sample["sign"], -1, 1)
        _require(sign != 0, "sign must be minus or plus one")
        h = _number(sample["h"], minimum=0)
        _require(h in steps, "sample step not declared")
        key = (i, axis, steps.index(h), sign)
        _require(key not in indexed, "duplicate sample")
        _require(_digest(sample["context_sha256"]) == context_hash, "sample context mismatch")
        _require(sample["status"] in ("ok", "failed", "unsupported", "not_attempted"), "unsupported sample status")
        record = {"status": sample["status"]}
        if sample["status"] == "ok":
            _require({"coordinates", "geometry_sha256", "energies"} <= set(sample), "missing successful sample fields")
            shifted = _coordinates(sample["coordinates"], n)
            _require(_digest(sample["geometry_sha256"]) == geometry_sha256(shifted), "sample geometry digest mismatch")
            expected = coords[i][axis] + sign * h
            _require(math.isfinite(expected), "displacement out of range")
            for j in range(n):
                for k in range(3):
                    target = expected if (j, k) == (i, axis) else coords[j][k]
                    _require(shifted[j][k].hex() == target.hex(), "sample is not the requested single-axis displacement")
            record.update(offset=sign * (shifted[i][axis] - coords[i][axis]),
                          energies=_channels(sample["energies"], terms))
        else:
            _require(not ({"coordinates", "geometry_sha256", "energies"} & set(sample)),
                     "unsuccessful sample must not carry numeric evidence")
        indexed[key] = record
    return n, terms, steps, policy, energies, forces, indexed


def _stencil(e0, ep, em, a, b, force, policy):
    if not math.isfinite(a) or not math.isfinite(b) or a <= 0 or b <= 0:
        return {"status": "unknown", "reason": "unresolved_displacement"}
    try:
        right = (ep - e0) / a
        left = (e0 - em) / b
        gradient = (b * right + a * left) / (a + b)
        fd = -gradient
        error = abs(force - fd)
        threshold = policy["force_atol"] + policy["force_rtol"] * max(abs(force), abs(fd))
        stable_threshold = policy["stability_atol"] + policy["stability_rtol"] * abs(fd)
        # A conservative float arithmetic proxy plus caller-declared absolute
        # energy uncertainty; this is not a certified bound on engine errors.
        noise = 8 * (math.ulp(e0) * 2 + math.ulp(ep) + math.ulp(em) +
                     4 * policy["energy_resolution"]) / min(a, b)
        slope_gap = abs(right - left)
        _require(all(math.isfinite(v) for v in (right, left, fd, error, threshold, noise,
                                                stable_threshold, slope_gap)), "nonfinite derived arithmetic")
    except (ArithmeticError, EvidenceError):
        return {"status": "unknown", "reason": "unresolved_arithmetic"}
    risk = noise > policy["roundoff_fraction"] * min(threshold, stable_threshold)
    return {"status": "unknown" if risk else "observed",
            "reason": "roundoff_or_energy_resolution" if risk else None,
            "force_fd": fd, "force_analytic": force, "absolute_error": error,
            "force_threshold": threshold, "within_force_policy": error <= threshold,
            "left_gradient": left, "right_gradient": right,
            "slope_gap": slope_gap, "roundoff_proxy": noise,
            "plus_offset": a, "minus_offset": b}


def analyze(data):
    """Analyze supplied evidence only; raises EvidenceError for invalid contracts."""
    n, terms, steps, policy, energies, forces, indexed = _validate(data)
    axes = []
    informative_axes = 0
    sample_counts = {state: 0 for state in ("ok", "failed", "unsupported", "not_attempted", "missing")}
    for i in range(n):
        for axis in range(3):
            for k in range(len(steps)):
                for sign in (-1, 1):
                    sample_counts[indexed.get((i, axis, k, sign), {"status": "missing"})["status"]] += 1
            for term_index, term in enumerate(terms):
                rows = []
                for k, h in enumerate(steps):
                    row = {"step_index": k, "h": h}
                    plus, minus = indexed.get((i, axis, k, 1)), indexed.get((i, axis, k, -1))
                    if term not in energies or term not in forces:
                        row.update(status="unknown", reason="baseline_channel_missing")
                    elif plus is None or minus is None:
                        row.update(status="unknown", reason="sample_missing")
                    elif plus["status"] != "ok" or minus["status"] != "ok":
                        row.update(status="unknown", reason="sample_not_successful")
                    elif term not in plus["energies"] or term not in minus["energies"]:
                        row.update(status="unknown", reason="sample_channel_missing")
                    else:
                        row.update(_stencil(energies[term], plus["energies"][term], minus["energies"][term],
                                            plus["offset"], minus["offset"], forces[term][i][axis], policy))
                    rows.append(row)
                reasons = []
                if policy["domain"] != "smooth":
                    reasons.append("smooth_domain_not_declared")
                if any(row["status"] != "observed" for row in rows):
                    reasons.append("incomplete_or_unresolved_stencils")
                stable = False
                slope_resolved = False
                informative = False
                if not any(row["status"] != "observed" for row in rows):
                    # All predeclared h values participate. No posthoc best-h selection.
                    stable = all(abs(a["force_fd"] - b["force_fd"]) <=
                                 policy["stability_atol"] + policy["stability_rtol"] *
                                 max(abs(a["force_fd"]), abs(b["force_fd"]))
                                 for a, b in zip(rows, rows[1:]))
                    if not stable:
                        reasons.append("finite_differences_not_stable")
                    # Central agreement alone cannot detect a cusp. Require final
                    # one-sided agreement under the caller's stability policy.
                    last = rows[-1]
                    slope_resolved = last["slope_gap"] <= policy["stability_atol"] + policy["stability_rtol"] * max(
                        abs(last["left_gradient"]), abs(last["right_gradient"]))
                    if not slope_resolved:
                        reasons.append("one_sided_slopes_unresolved")
                    informative = any(max(abs(row["force_fd"]), abs(row["force_analytic"])) >
                                      row["force_threshold"] for row in rows)
                if reasons:
                    status = "unknown"
                elif all(row["within_force_policy"] for row in rows):
                    status = "consistent_under_supplied_policy"
                else:
                    status = "inconsistent_under_supplied_policy"
                if informative and status != "unknown":
                    informative_axes += 1
                axes.append({"atom_index": i, "axis": axis, "term_index": term_index,
                             "status": status, "reasons": reasons, "informative_signal": informative,
                             "fd_ladder_stable": stable, "one_sided_slopes_resolved": slope_resolved,
                             "stencils": rows})
    counts = {status: sum(row["status"] == status for row in axes) for status in
              ("consistent_under_supplied_policy", "inconsistent_under_supplied_policy", "unknown")}
    if counts["unknown"] or informative_axes == 0:
        overall = "unknown"
    elif counts["inconsistent_under_supplied_policy"]:
        overall = "inconsistent_under_supplied_policy"
    else:
        overall = "consistent_under_supplied_policy"
    return {"schema": "saved_force_differences_report/1", "input_canonical_sha256": canonical_sha256(data),
            "context_sha256": data["context_sha256"], "policy_sha256": canonical_sha256(data["policy"]),
            "status": overall, "expected_axes": n * 3, "expected_axis_channels": n * 3 * len(terms),
            "expected_samples": 6 * n * len(steps), "sample_counts": sample_counts,
            "axis_channel_counts": counts, "informative_axis_channels": informative_axes,
            "required_h_count": len(steps), "coverage_complete": sample_counts["ok"] == 6 * n * len(steps)
            and all(term in energies and term in forces for term in terms)
            and all(set(record.get("energies", {})) == set(terms) for record in indexed.values()),
            "engine_evaluations_performed": 0, "engine_qualification": "not_performed",
            "scientific_validation": False, "producer_authenticity_verified": False,
            "axes": axes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="saved JSON evidence; no engine execution")
    parser.add_argument("--expected-sha256", required=True, help="expected SHA256 of exact input bytes")
    args = parser.parse_args(argv)
    try:
        _digest(args.expected_sha256)
        with Path(args.input).open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        _require(len(raw) <= MAX_BYTES, "input byte budget exceeded")
        _require(hashlib.sha256(raw).hexdigest() == args.expected_sha256, "input byte digest mismatch")
        report = analyze(load_bytes(raw))
        report["input_bytes_sha256"] = hashlib.sha256(raw).hexdigest()
        output = json.dumps(report, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n"
        _require(len(output.encode("utf-8")) <= MAX_OUTPUT_BYTES, "output byte budget exceeded")
        sys.stdout.write(output)
        return 0
    except (ValueError, OSError, UnicodeError, OverflowError, RecursionError):
        sys.stderr.write("saved force evidence rejected: invalid, inaccessible, or over budget\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
