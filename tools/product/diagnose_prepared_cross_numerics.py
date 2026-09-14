"""Attribute saved cross-force discrepancies without changing their verdict.

Decimal arithmetic starts from the exact binary64 input values, including the
declared Coulomb constant. It diagnoses arithmetic, not molecular preparation.
Optional one-pair projections call the existing V2 kernel; they are never an
independent oracle or a replacement for the original full-system calculation.
"""

from __future__ import annotations

import argparse
from decimal import Decimal as D, localcontext
import hashlib
import json
import math
from pathlib import Path
import time

try:
    from . import verify_prepared_cross_numerics as check
except ImportError:  # direct dependency-free script invocation
    import verify_prepared_cross_numerics as check


def decimal_pair(position, other, receptor, ligand, config, *, precision=80):
    """Independent analytic energy and receptor force, all input floats exact."""
    with localcontext() as ctx:
        ctx.prec = precision
        delta = [D(b) - D(a) for a, b in zip(position, other)]
        r = sum(x * x for x in delta).sqrt()
        cutoff, start, dielectric, kappa = map(D, config)
        if r >= cutoff:
            return D(0), (D(0),) * 3
        if r < D(0.35):
            raise ValueError("invalid_cross_distance")
        q1, s1, e1 = map(D, receptor)
        q2, s2, e2 = map(D, ligand)
        sigma, epsilon = (s1 + s2) / 2, (e1 * e2).sqrt()
        a6 = sigma**6 / r**6
        lj = 4 * epsilon * (a6**2 - a6)
        coul = D(332.063713299) * q1 * q2 * (-kappa * r).exp() / dielectric / r
        slope = 24 * epsilon * (a6 - 2 * a6**2) / r - coul * (kappa + 1 / r)
        switch, ds = D(1), D(0)
        if r > start:
            x = (r - start) / (cutoff - start)
            switch = 1 - 10 * x**3 + 15 * x**4 - 6 * x**5
            ds = (-30 * x**2 + 60 * x**3 - 30 * x**4) / (cutoff - start)
        return (lj + coul) * switch, tuple(
            (slope * switch + (lj + coul) * ds) * x / r for x in delta
        )


def _float_terms(result):
    receptor, rp = check._component(result["sources"]["receptor"])
    ligand, lp = check._component(result["sources"]["ligand"])
    config = tuple(
        result["model"][key]
        for key in (
            "cutoff_angstrom",
            "switch_start_angstrom",
            "dielectric",
            "screening_kappa_per_angstrom",
        )
    )
    forces = {"receptor": [[0.0] * 3 for _ in rp], "ligand": [[0.0] * 3 for _ in lp]}
    for i, a in enumerate(receptor):
        for j, b in enumerate(ligand):
            delta = [b[k] - a[k] for k in range(3)]
            r = math.sqrt(sum(x * x for x in delta))
            if r > config[0]:
                continue
            derivative = check._scalar_pair(r, rp[i], lp[j], *config)[2]
            for k in range(3):
                f = derivative * delta[k] / r
                forces["receptor"][i][k] += f
                forces["ligand"][j][k] -= f
    return receptor, ligand, rp, lp, config, forces


def _engine_pairs(result, indices, side, axis):
    import torch
    from betelgeuze_engine.product.v2_cross_interaction import _tile
    from betelgeuze_engine_v2.molecular.serialization import (
        all_atom_system_from_canonical_json,
    )

    sources = result["sources"]
    receptor, ligand = [
        all_atom_system_from_canonical_json(json.dumps(sources[key]["system"]))
        for key in ("receptor", "ligand")
    ]
    config = {
        key: result["model"][key]
        for key in (
            "cutoff_angstrom",
            "switch_start_angstrom",
            "dielectric",
            "screening_kappa_per_angstrom",
        )
    }
    values = []
    with torch.inference_mode(False), torch.enable_grad():
        for i, j in indices:
            _, forces, _ = _tile(
                receptor,
                ligand,
                [i],
                [j],
                sources["receptor"]["nonbonded_parameters"],
                sources["ligand"]["nonbonded_parameters"],
                config,
            )
            values.append(float(forces[0 if side == "receptor" else 1, axis]))
    return values



def _pair_finite_difference(position, other, receptor, ligand, config, axis, h):
    """Second-order derivative inside the unchanged minimum-distance domain.

    Differentiate by moving the ligand coordinate. The returned derivative is
    the receptor force; callers invert it for a ligand component. The historic
    central stencil is retained wherever both points are admissible.
    """
    with localcontext() as ctx:
        ctx.prec = 120
        origin, center = list(map(D, position)), list(map(D, other))
        def point(offset):
            value = center.copy()
            value[axis] += offset * h
            return value
        def allowed(value):
            return sum((b - a)**2 for a, b in zip(origin, value)).sqrt() >= D(0.35)
        def energy(value):
            return decimal_pair(origin, value, receptor, ligand, config, precision=120)[0]
        if allowed(point(1)) and allowed(point(-1)):
            return (energy(point(1)) - energy(point(-1))) / (2*h), "central"
        # A one-sided O(h^2) stencil avoids evaluating the forbidden domain.
        for sign, method in ((1, "forward"), (-1, "backward")):
            if allowed(point(sign)) and allowed(point(2*sign)):
                value = (-3*energy(center) + 4*energy(point(sign)) - energy(point(2*sign))) / (2*h*sign)
                return value, method
        return None, "unavailable_inside_declared_domain"


def diagnose_result(result, *, engine_pairs=False):
    original = check.check_result(result)
    receptor, ligand, rp, lp, config, reference = _float_terms(result)
    # Locate the actual maximum absolute discrepancy, not the largest force.
    maxima = []
    for side in ("receptor", "ligand"):
        observed = result["quantities"][side + "_cross_forces_kcal_per_mol_angstrom"]
        maxima.extend(
            (abs(actual[k] - expected[k]), side, i, k, actual[k], expected[k])
            for i, (actual, expected) in enumerate(zip(observed, reference[side]))
            for k in range(3)
        )
    maximum = max(x[0] for x in maxima)
    tied = [x for x in maxima if x[0] == maximum]
    _, side, index, axis, observed, naive = tied[0]
    terms, indices = [], []
    for i, a in enumerate(receptor):
        if side == "receptor" and i != index:
            continue
        for j, b in enumerate(ligand):
            if side == "ligand" and j != index:
                continue
            delta = [b[k] - a[k] for k in range(3)]
            r = math.sqrt(sum(x * x for x in delta))
            if r > config[0]:
                continue
            sign = 1 if side == "receptor" else -1
            f = sign * check._scalar_pair(r, rp[i], lp[j], *config)[2] * delta[axis] / r
            _, exact = decimal_pair(a, b, rp[i], lp[j], config)
            _, higher = decimal_pair(a, b, rp[i], lp[j], config, precision=120)
            with localcontext() as ctx:
                ctx.prec = 120
                exact_value, higher_value = sign * exact[axis], sign * higher[axis]
            indices.append((i, j))
            terms.append(
                {
                    "receptor_atom": i,
                    "ligand_atom": j,
                    "distance_angstrom": r,
                    "float_scalar_force": f,
                    "decimal80_force": str(exact_value),
                    "decimal120_force": str(higher_value),
                }
            )
    with localcontext() as ctx:
        ctx.prec = 120
        total80 = sum((D(x["decimal80_force"]) for x in terms), D(0))
        total120 = sum((D(x["decimal120_force"]) for x in terms), D(0))
        stable = abs(total80 - total120)
        engine_error = D(observed) - total120
        naive_error = D(naive) - total120
        nearest_error = abs(D(float(total120)) - total120)
    summed = math.fsum(x["float_scalar_force"] for x in terms)
    with localcontext() as ctx:
        ctx.prec = 120
        fsum_error = D(summed) - total120
        pair_errors = [
            D(x["float_scalar_force"]) - D(x["decimal120_force"]) for x in terms
        ]
        pair_error_sum = sum(pair_errors, D(0))
    dominant = (
        max(range(len(terms)), key=lambda k: abs(D(terms[k]["decimal120_force"])))
        if terms
        else None
    )
    finite_differences = []
    if dominant is not None:
        i, j = indices[dominant]
        for h in (D("1e-12"), D("1e-16")):
            with localcontext() as ctx:
                ctx.prec = 100
                fd, method = _pair_finite_difference(
                    receptor[i], ligand[j], rp[i], lp[j], config, axis, h
                )
                fd = None if fd is None else fd * (1 if side == "receptor" else -1)
                finite_differences.append(
                    {
                        "step_angstrom": str(h),
                        "status": "not_evaluated" if fd is None else "evaluated",
                        "method": method,
                        "force": None if fd is None else str(fd),
                        "abs_error": None if fd is None else str(
                            abs(fd - D(terms[dominant]["decimal120_force"]))
                        ),
                    }
                )
    isolated = None
    if engine_pairs:
        values = _engine_pairs(result, indices, side, axis)
        for term, value in zip(terms, values):
            term["isolated_existing_v2_force"] = value
        with localcontext() as ctx:
            ctx.prec = 120
            isolated = {
                "pair_count": len(values),
                "fsum": math.fsum(values),
                "observed_minus_isolated_pair_fsum": observed - math.fsum(values),
                "isolated_fsum_minus_decimal120": str(D(math.fsum(values)) - total120),
                "pair_arithmetic_error_sum": str(
                    sum(
                        (
                            D(v) - D(t["decimal120_force"])
                            for v, t in zip(values, terms)
                        ),
                        D(0),
                    )
                ),
                "scope": "one_pair_existing_kernel_projections; difference also includes full_tile_shape_and_reduction",
            }
    return {
        "original_check": original,
        "original_force_atol": check.FORCE_ATOL,
        "maximum_error_component": {
            "side": side,
            "atom_index": index,
            "axis": axis,
            "observed": observed,
            "scalar_naive": naive,
            "absolute_error": maximum,
            "ulp": math.ulp(observed),
        },
        "tied_maximum_components": [
            {"side": x[1], "atom_index": x[2], "axis": x[3]} for x in tied
        ],
        "decimal_input_semantics": "exact_reported_binary64_inputs_and_binary64_coulomb_constant",
        "decimal120_total": str(total120),
        "precision80_vs120_abs_delta": str(stable),
        "observed_minus_decimal120": str(engine_error),
        "naive_minus_decimal120": str(naive_error),
        "scalar_fsum": summed,
        "fsum_minus_decimal120": str(fsum_error),
        "naive_minus_fsum": naive - summed,
        "float_scalar_pair_error_sum": str(pair_error_sum),
        "nearest_float64_representation_error": str(nearest_error),
        "nearest_float64_cannot_meet_original_atol": nearest_error
        > D(check.FORCE_ATOL),
        "absolute_accuracy_support": (
            "unsupported_at_diagnosed_component"
            if nearest_error > D(check.FORCE_ATOL)
            else "not_determined_for_other_components"
        ),
        "dominant_pair_index": dominant,
        "dominant_pair_finite_differences": finite_differences,
        "isolated_existing_kernel": isolated,
        "pair_contributions": terms,
        "source_authenticated": False,
        "preparation_validated": False,
        "threshold_relaxed": False,
        "training_admitted": False,
        "scientifically_validated": False,
    }


def diagnose_report(report, *, engine_pairs=False):
    original = check.check_report(report)
    rows = []
    for row, verdict in zip(report["rows"], original["rows"]):
        item = {
            "request_index": verdict["request_index"],
            "case_id": row.get("case_id"),
            "calculation_status": row["status"],
        }
        if verdict["comparison_status"] in {"passed", "failed"}:
            item.update(
                status="diagnosed",
                diagnostic=diagnose_result(row["result"], engine_pairs=engine_pairs),
            )
        else:
            item.update(status="not_diagnosed", original_check=verdict)
        rows.append(item)
    return {
        "schema_version": "prepared_cross_force_diagnostic_v1",
        "original_check": original,
        "rows": rows,
        "denominator": {
            "requested": len(rows),
            "diagnosed": sum(x["status"] == "diagnosed" for x in rows),
        },
        "scope": "arithmetic_attribution_only",
        "training_admitted": False,
        "scientifically_validated": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--with-engine-pairs", action="store_true")
    args = parser.parse_args(argv)
    started = time.perf_counter()
    with args.report.open("rb") as stream:
        raw = stream.read(check.MAX_BYTES + 1)
    if len(raw) > check.MAX_BYTES:
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

    result = diagnose_report(
        json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite),
        engine_pairs=args.with_engine_pairs,
    )
    result.update(
        input_sha256=hashlib.sha256(raw).hexdigest(),
        checker_sha256=hashlib.sha256(Path(check.__file__).read_bytes()).hexdigest(),
        diagnostic_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        wall_seconds=time.perf_counter() - started,
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
