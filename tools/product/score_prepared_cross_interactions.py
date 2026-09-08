"""Offline prepared-state consumer for the existing Engine V2 cross kernel.

Invoke with ``python -m tools.product.score_prepared_cross_interactions``.
Source files must already be local and hash-bound. This command does not prepare
molecules, fetch data, load a learned model, or call an external solver.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time

SCHEMA = "prepared_cross_interaction_request_v1"


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def evaluate_request(request: dict) -> dict:
    """Retain every requested case, including unsupported or failed cases."""
    if (not isinstance(request, dict) or set(request) != {"schema_version", "cases"}
            or request["schema_version"] != SCHEMA or not isinstance(request["cases"], list)
            or not 1 <= len(request["cases"]) <= 32):
        raise ValueError("expected 1..32 cases under the prepared cross request contract")
    rows = []
    for index, case in enumerate(request["cases"]):
        started, cpu = time.perf_counter(), time.process_time()
        row = {"request_index": index, "case_id": case.get("case_id") if isinstance(case, dict) and type(case.get("case_id")) is str else None}
        try:
            if (not isinstance(case, dict) or set(case) != {"case_id", "prepared_input", "evaluation"}
                    or type(case["case_id"]) is not str or not case["case_id"].strip()
                    or not isinstance(case["evaluation"], dict)):
                raise ValueError("invalid case fields")
            evaluation = case["evaluation"]
            required = {"pocket_center_angstrom", "pocket_radius_angstrom", "cutoff_angstrom",
                        "switch_start_angstrom", "dielectric", "screening_kappa_per_angstrom"}
            if set(evaluation) != required:
                raise ValueError("all cross-model and pocket parameters must be explicit")
            from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
            from betelgeuze_engine.product.v2_cross_interaction import evaluate_prepared_cross_interaction
            receptor, ligand, rp, lp, provenance = load_prepared_gromacs_components(case["prepared_input"])
            result = evaluate_prepared_cross_interaction(
                receptor, ligand, rp, lp,
                source_declarations=case["prepared_input"]["source_declarations"], **evaluation)
            row.update(status="evaluated", result=result, preparation_provenance=provenance)
        except Exception as exc:
            row.update(status="failed", error_type=type(exc).__name__, reason=str(exc))
        row["cost"] = {"wall_seconds": time.perf_counter()-started,
                       "cpu_seconds": time.process_time()-cpu,
                       "scope": "case validation, any first-call lazy imports, parsing, hash validation and evaluation; output excluded"}
        rows.append(row)
    success = sum(row["status"] == "evaluated" for row in rows)
    return {"schema_version": "prepared_cross_interaction_report_v1", "rows": rows,
            "denominator": {"requested": len(rows), "evaluated": success,
                            "failed": len(rows)-success, "skipped": 0},
            "customer_execution": False, "scientifically_validated": False,
            "external_solver_called": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error("output must be a new path; existing evidence and source files are preserved")
    started, cpu = time.perf_counter(), time.process_time()
    request_sha = None
    try:
        raw = args.request.read_bytes()
        request_sha = hashlib.sha256(raw).hexdigest()
        request = json.loads(raw, object_pairs_hook=_strict_object,
                             parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"nonfinite JSON: {value}")))
        result = evaluate_request(request)
        if args.request.read_bytes() != raw:
            raise ValueError("request changed during evaluation")
        exit_code = 0 if result["denominator"]["failed"] == 0 else 2
    except Exception as exc:
        result = {"schema_version": "prepared_cross_interaction_report_v1", "status": "invalid_request",
                  "error_type": type(exc).__name__, "reason": str(exc), "denominator": None,
                  "customer_execution": False, "scientifically_validated": False,
                  "external_solver_called": False}
        exit_code = 2
    result["request_sha256"] = request_sha
    result["consumer_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["environment"] = {"python": sys.version, "platform": platform.platform()}
    result["process_observation"] = {"wall_seconds": time.perf_counter()-started,
        "cpu_seconds": time.process_time()-cpu,
        "peak_rss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "peak_rss_unit": "KiB" if sys.platform.startswith("linux") else "platform_native",
        "scope": "command main including imports, parsing and evaluation; process startup/output excluded"}
    result["exit_code"] = exit_code
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, sort_keys=True, indent=2, allow_nan=False)
        output.write("\n")
    print(json.dumps({"output": str(args.output), "exit_code": exit_code,
                      "denominator": result["denominator"]}, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
