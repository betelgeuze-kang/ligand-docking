"""Offline source-coordinate consumer; no training, physical scoring or solver."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import resource
import time

from betelgeuze_engine.product.mmcif_ligand_observation import observe_mmcif_ligand

SCHEMA = "mmcif_ligand_observation_request_v1"


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def evaluate_request(request):
    if (not isinstance(request, dict) or set(request) != {"schema_version", "cases"}
            or request["schema_version"] != SCHEMA or not isinstance(request["cases"], list)
            or not 1 <= len(request["cases"]) <= 32):
        raise ValueError("expected_1_to_32_source_observation_cases")
    counts = Counter(c.get("case_id") for c in request["cases"] if isinstance(c, dict) and isinstance(c.get("case_id"), str))
    rows = []
    for index, case in enumerate(request["cases"]):
        started, cpu = time.perf_counter(), time.process_time()
        row = {"request_index": index, "case_id": case.get("case_id") if isinstance(case, dict) else None,
               "status": "failed", "observation": None}
        rows.append(row)
        try:
            if (not isinstance(case, dict) or set(case) != {"case_id", "source", "selection", "provenance"}
                    or not isinstance(case["case_id"], str) or not case["case_id"].strip()
                    or counts[case["case_id"]] != 1 or not isinstance(case["provenance"], dict)):
                raise ValueError("invalid_or_duplicate_case")
            # Metadata is retained as declared; it cannot grant training admission.
            json.dumps(case["provenance"], allow_nan=False)
            row["provenance"] = case["provenance"]
            row["observation"] = observe_mmcif_ligand(source=case["source"], selection=case["selection"])
            row["status"] = "observed"
        except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
            row.update(error_type=type(exc).__name__, reason=str(exc))
        row["cost"] = {"wall_s": time.perf_counter() - started, "cpu_s": time.process_time() - cpu,
                       "scope": "source_read_hash_parse_identity_join_coordinate_geometry_postflight_excludes_process_import_and_output"}
    observed = sum(r["status"] == "observed" for r in rows)
    return {"schema_version": "mmcif_ligand_observation_report_v1", "rows": rows,
            "denominator": {"requested": len(rows), "observed": observed, "failed": len(rows) - observed, "skipped": 0,
                            "physical_evaluations": 0}, "external_solver_called": False,
            "scientifically_validated": False, "customer_execution": False,
            "environment": {"python": platform.python_version(), "platform": platform.platform(),
                            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    def nonfinite(value):
        raise ValueError("nonfinite_json:" + value)
    request = json.loads(args.request.read_text(), object_pairs_hook=_object, parse_constant=nonfinite)
    result = evaluate_request(request)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return 0 if result["denominator"]["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
