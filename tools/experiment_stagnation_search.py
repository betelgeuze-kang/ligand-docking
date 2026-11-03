#!/usr/bin/env python3
"""Fixed-budget scalar synthetic experiment, never a docking benchmark."""
import argparse
import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path

from stagnation_search_controller import Controller, ContractError, POLICIES

OBJECTIVES = ("convex", "planted_double_well", "periodic_wells")
FIELDS = {"schema", "policies", "objectives", "seeds", "budget", "patience", "improvement_epsilon",
          "restart_interval", "maximum_actions", "domain", "gradient_step", "maximum_step",
          "escape_radius", "success_threshold"}


def objective(name, x):
    if name == "convex":
        return (x - 0.75) ** 2, 2 * (x - 0.75)
    if name == "planted_double_well":
        return (x + 1) ** 2 * ((x - 1) ** 2 + 0.15), 2 * (x + 1) * ((x - 1) ** 2 + 0.15) + 2 * (x - 1) * (x + 1) ** 2
    if name == "periodic_wells":
        return 1 - math.cos(3 * x) + 0.05 * x * x, 3 * math.sin(3 * x) + 0.1 * x
    raise ContractError("unknown synthetic objective")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON key")
        result[key] = value
    return result


def load_protocol(raw):
    if len(raw) > 65536:
        raise ContractError("protocol byte limit")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ContractError("nonfinite JSON")))
    except (ValueError, UnicodeError, RecursionError):
        raise ContractError("invalid protocol JSON") from None
    return validate_protocol(value)


def validate_protocol(p):
    if not isinstance(p, dict) or set(p) != FIELDS or p["schema"] != "stagnation_search_toy_protocol/1":
        raise ContractError("invalid protocol fields")
    for key, allowed in (("policies", POLICIES), ("objectives", OBJECTIVES)):
        if not isinstance(p[key], list) or not p[key] or any(type(v) is not str for v in p[key]) or len(set(p[key])) != len(p[key]) or not set(p[key]) <= set(allowed):
            raise ContractError("invalid protocol categories")
    if not isinstance(p["seeds"], list) or not 1 <= len(p["seeds"]) <= 200 or any(type(v) is not int or not 0 <= v < 2**63 for v in p["seeds"]) or len(set(p["seeds"])) != len(p["seeds"]):
        raise ContractError("invalid seeds")
    if type(p["budget"]) is not int or not 1 <= p["budget"] <= 1000:
        raise ContractError("experiment budget limit")
    if p["budget"] * len(p["seeds"]) * len(p["objectives"]) * len(p["policies"]) > 600000:
        raise ContractError("total experiment limit")
    if not isinstance(p["domain"], list) or len(p["domain"]) != 2:
        raise ContractError("invalid domain")
    for value in p["domain"] + [p[k] for k in ("gradient_step", "maximum_step", "escape_radius", "success_threshold")]:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ContractError("invalid numeric protocol")
        try:
            finite = math.isfinite(value)
        except (ValueError, OverflowError):
            finite = False
        if not finite:
            raise ContractError("invalid numeric protocol")
    lo, hi = p["domain"]
    if not -10 <= lo < hi <= 10 or not lo < -1 < 0 < 0.75 < hi:
        raise ContractError("domain must contain all synthetic minimizers")
    if any(not 0 < p[key] <= 10 for key in ("gradient_step", "maximum_step", "escape_radius")) or not 0 <= p["success_threshold"] <= 1:
        raise ContractError("invalid adapter policy")
    Controller(p["policies"][0], p["budget"], patience=p["patience"], improvement_epsilon=p["improvement_epsilon"], restart_interval=p["restart_interval"], maximum_actions=p["maximum_actions"])
    return p


def _uniform(seed, kind, index, lo, hi):
    # Counter-keyed action streams; policy iteration order never consumes RNG.
    key = hashlib.sha256(f"{seed}:{kind}:{index}".encode("ascii")).digest()
    return random.Random(int.from_bytes(key, "big")).uniform(lo, hi)


def run_case(p, name, seed, policy):
    controller = Controller(policy, p["budget"], patience=p["patience"], improvement_epsilon=p["improvement_epsilon"], restart_interval=p["restart_interval"], maximum_actions=p["maximum_actions"])
    x = energy = gradient = initial = None
    best_energy = best_x = None
    counts = {kind: 0 for kind in ("initialize", "refine", "restart", "escape")}
    calls = 0
    visits = set()
    while True:
        action = controller.issue()
        if action is None:
            break
        kind = action["kind"]
        index = counts[kind]
        counts[kind] += 1
        lo, hi = p["domain"]
        if kind in ("initialize", "restart"):
            candidate = _uniform(seed, kind, index, lo, hi)
        elif kind == "escape":
            candidate = x + _uniform(seed, kind, index, -p["escape_radius"], p["escape_radius"])
        else:
            displacement = max(-p["maximum_step"], min(p["maximum_step"], -p["gradient_step"] * gradient))
            candidate = x + displacement
        candidate = max(lo, min(hi, candidate))
        candidate_energy, candidate_gradient = objective(name, candidate)
        calls += 1  # A joint E/gradient call; all initialization/rejected moves count.
        accepted = kind != "refine" or energy is None or candidate_energy <= energy
        controller.observe(action["action_id"], status="ok", evaluations=1,
                           energy=candidate_energy, accepted=accepted)
        if best_energy is None or candidate_energy < best_energy:
            best_energy, best_x = candidate_energy, candidate
        if accepted:
            x, energy, gradient = candidate, candidate_energy, candidate_gradient
        if initial is None:
            initial = candidate
        visits.add(math.floor(candidate))  # Only post-observation descriptive bins.
    snapshot = controller.snapshot()
    return {"objective": name, "seed": seed, "policy": policy, "initial_x": initial,
            "best_energy": best_energy, "best_x": best_x, "final_energy": energy,
            "actual_joint_ef_calls": calls, "success": best_energy is not None and best_energy <= p["success_threshold"],
            "visited_coordinate_bins": len(visits), "controller": snapshot,
            "complete_budget": calls == p["budget"], "failure": None}


def experiment(protocol):
    p = validate_protocol(protocol)
    rows = [run_case(p, name, seed, policy) for name in p["objectives"] for seed in p["seeds"] for policy in p["policies"]]
    summaries = []
    for name in p["objectives"]:
        for policy in p["policies"]:
            chosen = [r for r in rows if r["objective"] == name and r["policy"] == policy]
            values = [r["best_energy"] for r in chosen]
            summaries.append({"objective": name, "policy": policy, "expected_cases": len(p["seeds"]),
                              "observed_cases": len(chosen), "failures": sum(r["failure"] is not None for r in chosen),
                              "successes": sum(r["success"] for r in chosen),
                              "best_energy_median": statistics.median(values), "best_energy_range": [min(values), max(values)],
                              "cost_range": [min(r["actual_joint_ef_calls"] for r in chosen), max(r["actual_joint_ef_calls"] for r in chosen)],
                              "incomplete_budgets": sum(not r["complete_budget"] for r in chosen)})
    return {"schema": "stagnation_search_toy_report/1", "protocol": p,
            "protocol_canonical_sha256": hashlib.sha256(json.dumps(p, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
            "cost_unit": "one joint analytic energy/gradient oracle call",
            "molecular_evaluations": 0, "molecular_adapter_connected": False,
            "scientific_validation": False, "reference_used_by_controller": False,
            "expected_cases": len(p["objectives"]) * len(p["seeds"]) * len(p["policies"]),
            "summary": summaries, "cases": rows}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("protocol")
    ap.add_argument("--expected-sha256", required=True)
    args = ap.parse_args(argv)
    try:
        if len(args.expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in args.expected_sha256):
            raise ContractError("invalid digest")
        with Path(args.protocol).open("rb") as stream:
            raw = stream.read(65537)
        if hashlib.sha256(raw).hexdigest() != args.expected_sha256:
            raise ContractError("protocol digest mismatch")
        report = experiment(load_protocol(raw))
        report["protocol_bytes_sha256"] = args.expected_sha256
        output = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(output.encode()) > 16 * 1024 * 1024:
            raise ContractError("output limit")
        print(output)
        return 0
    except (ContractError, OSError, ValueError, OverflowError, RecursionError):
        sys.stderr.write("synthetic search experiment rejected: invalid, inaccessible, or over budget\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
