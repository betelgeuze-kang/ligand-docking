"""Read-only scalar arithmetic check of saved prepared cross-interaction reports.

This independent Python reference does not import the engine, use its reported
pair list to select work, repair coordinates, or confer scientific/training
approval. Fixed absolute tolerances retain the original PFK40 audit criterion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import time

ENERGY_ATOL = 1e-8
FORCE_ATOL = 1e-8
MAX_BYTES = 256 * 1024 * 1024
MAX_PAIRS = 2_000_000
REPORT_SCHEMAS = {
    "prepared_cross_interaction_report_v1", "prepared_cross_interaction_report_v2",
    "prepared_rigid_pose_cross_report_v1",
}


def _finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("expected_finite_number")
    return float(value)


def _vector(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("expected_three_vector")
    return [_finite(x) for x in value]


def _component(source):
    parameters = source["nonbonded_parameters"]
    if type(parameters) is not list or not 1 <= len(parameters) <= 16384:
        raise ValueError("unsupported_atom_count")
    parsed = []
    for index, row in enumerate(parameters):
        if type(row["atom_index"]) is not int or row["atom_index"] != index:
            raise ValueError("invalid_parameter_index")
        charge, sigma, epsilon = (_finite(row[k]) for k in
                                  ("charge_e", "sigma_angstrom", "epsilon_kcal_per_mol"))
        if sigma < 0 or epsilon < 0 or (sigma == 0 and epsilon != 0):
            raise ValueError("invalid_nonbonded_parameters")
        parsed.append((charge, sigma, epsilon))
    tensor = source["system"]["system"]["coordinates"]["coordinates"]["$tensor"]
    shape = tensor["shape"]
    if (tensor["dtype"] != "float64" or type(shape) is not list
            or any(type(x) is not int for x in shape) or shape != [1, len(parsed), 3]
            or len(tensor["values"]) != 3 * len(parsed)):
        raise ValueError("unsupported_coordinate_tensor")
    values = []
    for item in tensor["values"]:
        if (type(item) is not dict or set(item) != {"$float_hex"}
                or type(item["$float_hex"]) is not str or len(item["$float_hex"]) > 80):
            raise ValueError("invalid_coordinate_scalar")
        values.append(_finite(float.fromhex(item["$float_hex"])))
    return [values[i:i + 3] for i in range(0, len(values), 3)], parsed


def _scalar_pair(distance, receptor, ligand, cutoff, switch_start, dielectric, kappa):
    if distance >= cutoff:
        return 0.0, 0.0, 0.0
    sigma = (receptor[1] + ligand[1]) / 2.0
    epsilon = math.sqrt(receptor[2] * ligand[2])
    a6 = (sigma / distance) ** 6
    lj = 4.0 * epsilon * (a6 * a6 - a6)
    d_lj = 24.0 * epsilon * (a6 - 2.0 * a6 * a6) / distance
    coefficient = 332.063713299 * receptor[0] * ligand[0] / dielectric
    coulomb = coefficient * math.exp(-kappa * distance) / distance
    d_coulomb = -coulomb * (kappa + 1.0 / distance)
    switch, derivative = 1.0, 0.0
    if distance > switch_start:
        x = (distance - switch_start) / (cutoff - switch_start)
        switch = 1.0 - 10.0 * x ** 3 + 15.0 * x ** 4 - 6.0 * x ** 5
        derivative = (-30.0 * x ** 2 + 60.0 * x ** 3 - 30.0 * x ** 4) / (cutoff - switch_start)
    return (lj * switch, coulomb * switch,
            (d_lj + d_coulomb) * switch + (lj + coulomb) * derivative)


def check_result(result):
    """Compare declared scalar model, every cross pair, energy and forces."""
    model = result["model"]
    if (result["status"] != "evaluated"
            or model["id"] != "existing_v2_switched_cross_lj_screened_coulomb_v1"
            or model["mixing"] != "Lorentz-Berthelot" or model["periodic"] is not False
            or _finite(model["cross_pair_scaling"]) != 1.0
            or _finite(model["minimum_pair_distance_angstrom"]) != 0.35):
        raise ValueError("unsupported_model")
    cutoff, start, dielectric, kappa = (_finite(model[k]) for k in (
        "cutoff_angstrom", "switch_start_angstrom", "dielectric", "screening_kappa_per_angstrom"))
    if not 0 < start < cutoff <= 20 or dielectric <= 0 or kappa < 0:
        raise ValueError("invalid_model_configuration")
    receptor, rp = _component(result["sources"]["receptor"])
    ligand, lp = _component(result["sources"]["ligand"])
    if len(rp) * len(lp) > MAX_PAIRS:
        raise ValueError("reference_pair_capacity_exceeded")
    rf, lf = [[0.0] * 3 for _ in rp], [[0.0] * 3 for _ in lp]
    energies, pairs = [[], []], []
    for i, position in enumerate(receptor):
        for j, other in enumerate(ligand):
            delta = [other[k] - position[k] for k in range(3)]
            distance = math.sqrt(sum(x * x for x in delta))
            if not math.isfinite(distance) or distance < 0.35:
                raise ValueError("invalid_cross_distance")
            if distance > cutoff:
                continue
            pairs.append([i, j])
            lj, coul, derivative = _scalar_pair(distance, rp[i], lp[j], cutoff, start, dielectric, kappa)
            energies[0].append(_finite(lj))
            energies[1].append(_finite(coul))
            for axis in range(3):
                force = _finite(derivative * delta[axis] / distance)
                rf[i][axis] += force
                lf[j][axis] -= force
    lj, coul = (math.fsum(values) for values in energies)
    quantities = result["quantities"]
    energy_errors = [abs(_finite(_finite(quantities[key]) - _finite(expected))) for key, expected in (
        ("cross_lennard_jones_kcal_per_mol", lj), ("cross_screened_coulomb_kcal_per_mol", coul),
        ("cross_total_kcal_per_mol", math.fsum([lj, coul])))]
    force_error = 0.0
    for side, reference in (("receptor", rf), ("ligand", lf)):
        observed = quantities[side + "_cross_forces_kcal_per_mol_angstrom"]
        if type(observed) is not list or len(observed) != len(reference):
            raise ValueError("invalid_force_shape")
        for actual, expected in zip(observed, reference):
            force_error = max(force_error, *(abs(_finite(a - _finite(b))) for a, b in zip(_vector(actual), expected)))
    accounting = result["pair_accounting"]
    # Recompute pair membership independently, including zero-energy cutoff pairs.
    declared_pairs = accounting["cross_pair_indices"]
    if (type(declared_pairs) is not list or any(type(pair) is not list or len(pair) != 2
            or any(type(index) is not int for index in pair) for pair in declared_pairs)):
        raise ValueError("invalid_pair_indices")
    pairs_exact = (declared_pairs == pairs
                   and type(accounting["requested_cross_pairs"]) is int
                   and accounting["requested_cross_pairs"] == len(rp) * len(lp)
                   and type(accounting["within_declared_cutoff"]) is int
                   and accounting["within_declared_cutoff"] == len(pairs))
    passed = max(energy_errors) <= ENERGY_ATOL and force_error <= FORCE_ATOL and pairs_exact
    return {"comparison_status": "passed" if passed else "failed",
            "energy_max_abs_error": max(energy_errors), "force_max_abs_error": force_error,
            "pairs_exact": pairs_exact, "reference_pair_count": len(pairs)}


def check_report(report):
    if (type(report) is not dict or report.get("schema_version") not in REPORT_SCHEMAS
            or type(report.get("rows")) is not list or not 1 <= len(report["rows"]) <= 32):
        raise ValueError("unsupported_report")
    denominator = report.get("denominator")
    if (type(denominator) is not dict
            or set(denominator) != {"requested", "evaluated", "failed", "skipped"}
            or any(type(x) is not int or x < 0 for x in denominator.values())
            or denominator["requested"] != len(report["rows"])
            or denominator["requested"] != sum(denominator[k] for k in ("evaluated", "failed", "skipped"))
            or any(not isinstance(row, dict) or row.get("status") not in {"evaluated", "failed", "skipped"}
                   for row in report["rows"])
            or any(denominator[k] != sum(row["status"] == k for row in report["rows"])
                   for k in ("evaluated", "failed", "skipped"))):
        raise ValueError("inconsistent_report_denominator")
    rows = []
    for index, row in enumerate(report["rows"]):
        item = {"request_index": index, "calculation_status": row.get("status") if isinstance(row, dict) else None}
        if not isinstance(row, dict) or row.get("status") != "evaluated":
            item["comparison_status"] = "not_run"
        else:
            try:
                item.update(check_result(row["result"]))
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                item.update(comparison_status="invalid_or_unsupported", error_type=type(exc).__name__)
        rows.append(item)
    passed = sum(row["comparison_status"] == "passed" for row in rows)
    return {"schema_version": "prepared_cross_numeric_check_v1", "rows": rows,
            "status": "passed" if passed == len(rows) else "not_passed",
            "denominator": {"requested": len(rows), "passed": passed,
                            "failed": sum(x["comparison_status"] == "failed" for x in rows),
                            "not_compared": sum(x["comparison_status"] in {"not_run", "invalid_or_unsupported"} for x in rows)},
            "absolute_energy_tolerance_kcal_per_mol": ENERGY_ATOL,
            "absolute_force_tolerance_kcal_per_mol_angstrom": FORCE_ATOL,
            "scope": "independent_scalar_arithmetic_on_reported_inputs_only",
            "source_authenticated": False, "physical_validity_assessed": False,
            "training_admitted": False, "scientifically_validated": False,
            "external_solver_called": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    with args.report.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("report_capacity_exceeded")
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError("duplicate_json_key")
            obj[key] = value
        return obj
    def nonfinite(_):
        raise ValueError("nonfinite_json_number")
    result = check_report(json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite))
    result["input_sha256"] = hashlib.sha256(raw).hexdigest()
    result["checker_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["wall_seconds"] = time.perf_counter() - started
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
