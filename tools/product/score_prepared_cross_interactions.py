"""Offline prepared-state consumer for the existing Engine V2 cross kernel.

Invoke with ``python -m tools.product.score_prepared_cross_interactions``.
Source files must already be local and hash-bound. This command does not prepare
molecules, fetch data, or call an external solver. The explicit shadow request
version can additionally execute the registered public assay predictor.
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
SHADOW_SCHEMA = "prepared_cross_interaction_with_assay_shadow_request_v1"


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def evaluate_request(request: dict) -> dict:
    """Retain every requested case, including unsupported or failed cases."""
    shadow_enabled = isinstance(request, dict) and request.get("schema_version") == SHADOW_SCHEMA
    fields = {"schema_version", "cases"} | ({"assay_selector"} if shadow_enabled else set())
    if (not isinstance(request, dict) or set(request) != fields
            or request["schema_version"] not in {SCHEMA, SHADOW_SCHEMA} or not isinstance(request["cases"], list)
            or not 1 <= len(request["cases"]) <= 32):
        raise ValueError("expected 1..32 cases under the prepared cross request contract")
    shadow_rows, shadow_summary = None, None
    if shadow_enabled:
        from betelgeuze_engine.product.prepared_assay_shadow import evaluate_assay_shadow
        shadow_rows, shadow_summary = evaluate_assay_shadow(request["cases"], request["assay_selector"])
    rows = []
    for index, case in enumerate(request["cases"]):
        started, cpu = time.perf_counter(), time.process_time()
        row = {"request_index": index, "case_id": case.get("case_id") if isinstance(case, dict) and type(case.get("case_id")) is str else None}
        if shadow_enabled:
            row["assay_selector_shadow"] = shadow_rows[index]
        row["source_geometry_observation"] = {
            "schema_version": "prepared_source_geometry_observation_v1",
            "status": "unavailable", "reason": "prepared_input_not_loaded", "groups": None,
            "physical_validity_assessed": False, "affects_score_or_admission": False}
        try:
            case_fields = {"case_id", "prepared_input", "evaluation"}
            if shadow_enabled and isinstance(case, dict) and "assay_metadata" in case:
                case_fields.add("assay_metadata")
            if (not isinstance(case, dict) or set(case) != case_fields
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
            from betelgeuze_engine.product.compiled_gromacs_cross_input import (
                SCHEMA as COMPILED_SCHEMA, load_compiled_gromacs_cross_particles,
            )
            loader = (load_compiled_gromacs_cross_particles
                      if isinstance(case["prepared_input"], dict) and case["prepared_input"].get("schema_version") == COMPILED_SCHEMA
                      else load_prepared_gromacs_components)
            receptor, ligand, rp, lp, provenance = loader(case["prepared_input"])
            row["preparation_provenance"] = provenance
            try:
                from betelgeuze_engine.product.prepared_source_geometry import observe_prepared_source_geometry
                row["source_geometry_observation"] = observe_prepared_source_geometry(receptor, ligand, provenance)
            except Exception as exc:
                row["source_geometry_observation"].update(
                    reason="source_geometry_observation_failed", error_type=type(exc).__name__, detail=str(exc))
            result = evaluate_prepared_cross_interaction(
                receptor, ligand, rp, lp,
                source_declarations=case["prepared_input"]["source_declarations"], **evaluation)
            row.update(status="evaluated", result=result)
        except Exception as exc:
            row.update(status="failed", error_type=type(exc).__name__, reason=str(exc))
        row["cost"] = {"wall_seconds": time.perf_counter()-started,
                       "cpu_seconds": time.process_time()-cpu,
                       "scope": "case validation, any first-call lazy imports, parsing, hash validation, source geometry observation and evaluation; output excluded"}
        rows.append(row)
    success = sum(row["status"] == "evaluated" for row in rows)
    report = {"schema_version": "prepared_cross_interaction_report_v1", "rows": rows,
            "denominator": {"requested": len(rows), "evaluated": success,
                            "failed": len(rows)-success, "skipped": 0},
            "customer_execution": False, "scientifically_validated": False,
            "external_solver_called": False}
    if shadow_enabled:
        report["schema_version"] = "prepared_cross_interaction_with_assay_shadow_report_v1"
        report["assay_selector_shadow"] = shadow_summary
    return report


def _write_report_json(result: dict, output) -> None:
    """Keep the full JSON payload while encoding at most one case at a time."""
    options = {"sort_keys": True, "separators": (",", ":"), "allow_nan": False}
    output.write("{")
    for index, key in enumerate(sorted(result)):
        if index:
            output.write(",")
        output.write(json.dumps(key) + ":")
        value = result[key]
        if key == "rows" and isinstance(value, list):
            output.write("[")
            for row_index, row in enumerate(value):
                if row_index:
                    output.write(",")
                output.write(json.dumps(row, **options))
            output.write("]")
        else:
            output.write(json.dumps(value, **options))
    output.write("}\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-format", choices=("pretty", "compact"), default="pretty",
                        help="JSON representation only; compact preserves every field and encodes one case at a time")
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
        shadow_unsupported = result.get("assay_selector_shadow", {}).get("denominator", {}).get("unsupported", 0)
        exit_code = 0 if result["denominator"]["failed"] == 0 and shadow_unsupported == 0 else 2
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
        if args.output_format == "compact":
            _write_report_json(result, output)
        else:
            json.dump(result, output, sort_keys=True, indent=2, allow_nan=False)
            output.write("\n")
    print(json.dumps({"output": str(args.output), "exit_code": exit_code,
                      "denominator": result["denominator"]}, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
