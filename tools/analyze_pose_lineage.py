#!/usr/bin/env python3
"""Descriptive, offline initial -> refined -> selected research-export adapter.

Only declared metrics are consumed. No molecular alignment, scoring, clustering,
source authentication, benchmark admission, or scientific promotion is performed.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys

SCHEMA = "betelgeuze.pose_lineage_export/1"
REPORT_SCHEMA = "betelgeuze.pose_lineage_report/1"
MAX_BYTES = 4 * 1024 * 1024
MAX_CASES = 256
MAX_CANDIDATES = 1024
MAX_TOTAL_CANDIDATES = 16384
STATUSES = ("ok", "failed", "missing", "not_attempted")
UNKNOWN = "UNKNOWN"


class LineageError(ValueError):
    """Invalid or incomparable research export."""


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise LineageError("object fields do not match the export contract")


def _identifier(value):
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,127}", value) is None:
        raise LineageError("identifier must be 1..128 printable identifier characters")
    return value


def _ids(value, limit, *, nonempty=True):
    if type(value) is not list or len(value) > limit or (nonempty and not value):
        raise LineageError("identifier list is empty or exceeds its bound")
    for item in value:
        _identifier(item)
    if len(set(value)) != len(value):
        raise LineageError("duplicate identifier")
    return value


def _number(value, *, positive=False):
    if type(value) not in (int, float):
        raise LineageError("metric must be numeric, not boolean")
    try:
        finite = math.isfinite(value)
    except OverflowError as exc:
        raise LineageError("metric is outside finite range") from exc
    if not finite or value < 0 or (positive and value == 0):
        raise LineageError("metric must be finite and nonnegative")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LineageError("duplicate JSON key")
        result[key] = value
    return result


def _constant(_value):
    raise LineageError("nonfinite JSON constant")


def _json_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise LineageError("nonfinite JSON number")
    return number


def parse_export(raw: bytes):
    """Parse bounded UTF-8 JSON; duplicate keys and nonfinite values fail closed."""
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise LineageError("input must be bytes within the 4 MiB limit")
    depth, quoted, escaped = 0, False, False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (91, 123):
            depth += 1
            if depth > 16:
                raise LineageError("JSON nesting exceeds the 16-level bound")
        elif char in (93, 125):
            depth -= 1
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_float=_json_float)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise LineageError("invalid research-export JSON") from exc


def _stage(value, context):
    _fields(value, "status metric validity convergence")
    if value["status"] not in STATUSES:
        raise LineageError("invalid stage status")
    if value["validity"] not in ("valid", "invalid", "unknown"):
        raise LineageError("invalid declared validity")
    if value["convergence"] not in ("converged", "not_converged", "unknown"):
        raise LineageError("invalid declared convergence")
    metric = value["metric"]
    if value["status"] != "ok":
        if metric is not None or value["validity"] != "unknown" or value["convergence"] != "unknown":
            raise LineageError("unavailable stages cannot declare pose evidence")
    if metric is not None:
        _fields(metric, "rmsd_angstrom reference_id frame_id mapping_id method_id source_id")
        _number(metric["rmsd_angstrom"])
        for key in ("reference_id", "frame_id", "mapping_id", "method_id"):
            _identifier(metric[key])
            if metric[key] != context[key]:
                raise LineageError("metric reference/frame/mapping/method is incomparable")
        _identifier(metric["source_id"])
    return value


def _missing():
    return dict(status="missing", metric=None, validity="unknown", convergence="unknown")


def _success(stage, threshold):
    if stage["status"] in ("failed", "not_attempted"):
        return False
    if stage["status"] == "missing":
        return None
    if stage["validity"] == "invalid":
        return False
    metric = stage["metric"]
    if metric is None or stage["validity"] == "unknown":
        return None
    return metric["rmsd_angstrom"] <= threshold


def _any(values):
    # A witnessed hit is useful even with incomplete coverage; a miss needs all rows.
    return True if True in values else (None if None in values else False)


def _transition(before, after):
    if before is None or after is None:
        return UNKNOWN
    return {(False, True): "recovery", (True, False): "loss",
            (True, True): "retained", (False, False): "no_success"}[before, after]


def analyze_export(document):
    """Validate and summarize a JSON-shaped export, preserving manifest denominators."""
    _fields(document, "schema_id unit threshold_angstrom top_k manifest cases")
    if document["schema_id"] != SCHEMA or document["unit"] != "angstrom":
        raise LineageError("unsupported schema or unit")
    threshold = _number(document["threshold_angstrom"], positive=True)
    if document["top_k"] != [1, 5] or any(type(k) is not int for k in document["top_k"]):
        raise LineageError("top_k must be the explicit [1, 5] analysis policy")
    manifest = document["manifest"]
    if type(manifest) is not list or not 1 <= len(manifest) <= MAX_CASES:
        raise LineageError("manifest case count is outside bounds")
    expected = {}
    total = 0
    for item in manifest:
        _fields(item, "case_id candidate_ids reference_id frame_id mapping_id method_id")
        case_id = _identifier(item["case_id"])
        if case_id in expected:
            raise LineageError("duplicate manifest case")
        _ids(item["candidate_ids"], MAX_CANDIDATES)
        total += len(item["candidate_ids"])
        for key in ("frame_id", "mapping_id", "method_id"):
            _identifier(item[key])
        if item["reference_id"] is not None:
            _identifier(item["reference_id"])
        expected[case_id] = item
    if total > MAX_TOTAL_CANDIDATES:
        raise LineageError("total candidate count exceeds bound")
    if type(document["cases"]) is not list or len(document["cases"]) > len(expected):
        raise LineageError("case observations exceed manifest")
    observed = {}
    for case in document["cases"]:
        _fields(case, "case_id candidates selected_ids")
        cid = _identifier(case["case_id"])
        if cid not in expected or cid in observed:
            raise LineageError("unexpected or duplicate observed case")
        context = expected[cid]
        if type(case["candidates"]) is not list or len(case["candidates"]) > len(context["candidate_ids"]):
            raise LineageError("candidate observations exceed manifest")
        candidates = {}
        for candidate in case["candidates"]:
            _fields(candidate, "candidate_id initial refined")
            key = _identifier(candidate["candidate_id"])
            if key not in context["candidate_ids"] or key in candidates:
                raise LineageError("unexpected or duplicate candidate")
            for stage in ("initial", "refined"):
                _stage(candidate[stage], context)
            candidates[key] = candidate
        selected = case["selected_ids"]
        if selected is not None:
            _ids(selected, MAX_CANDIDATES, nonempty=False)
            if any(key not in candidates or candidates[key]["refined"]["status"] != "ok" for key in selected):
                raise LineageError("selection must refer to observed refined poses")
        observed[cid] = (candidates, selected)
    rows = []
    for cid, context in expected.items():
        candidates, selected = observed.get(cid, ({}, None))
        lineage = []
        for key in context["candidate_ids"]:
            candidate = candidates.get(key, dict(candidate_id=key, initial=_missing(), refined=_missing()))
            before = _success(candidate["initial"], threshold)
            after = _success(candidate["refined"], threshold)
            # Without a reference, geometric conclusions are always UNKNOWN.
            if context["reference_id"] is None:
                before = after = None
            lineage.append({**candidate, "initial_success": before, "refined_success": after,
                            "transition": _transition(before, after),
                            "selected_rank": None if selected is None or key not in selected else selected.index(key) + 1})
        initial = _any([row["initial_success"] for row in lineage])
        refined = _any([row["refined_success"] for row in lineage])
        by_id = {row["candidate_id"]: row for row in lineage}
        top = {str(k): None if selected is None or context["reference_id"] is None else
               _any([by_id[key]["refined_success"] for key in selected[:k]]) for k in (1, 5)}
        selection_loss = None if refined is None or top["1"] is None else refined and not top["1"]
        rows.append({"case_id": cid, "context": context, "candidate_denominator": len(lineage),
                     "case_observed": cid in observed, "selected_ids": selected,
                     "initial_coverage_success": initial, "refined_coverage_success": refined,
                     "refinement_transition": _transition(initial, refined),
                     "top_k_success": top, "selection_loss": selection_loss,
                     "status_counts": {stage: {s: sum(row[stage]["status"] == s for row in lineage)
                                                for s in STATUSES} for stage in ("initial", "refined")},
                     "candidates": lineage})
    return {"schema_id": REPORT_SCHEMA, "scope": "declared_local_research_export_only",
            "source_authentication_performed": False, "scientifically_validated": False,
            "benchmark_gate_authority": False, "causal_inference": False,
            "policy": {"unit": "angstrom", "threshold_angstrom": threshold, "top_k": [1, 5],
                       "success": "declared_valid_and_rmsd_lte_threshold; convergence_is_separate"},
            "case_denominator": len(rows), "candidate_denominator": total,
            "case_transition_counts": dict(sorted(Counter(row["refinement_transition"] for row in rows).items())),
            "cases": rows}


def analyze_bytes(raw: bytes):
    """Bind a report to the actual export bytes (not to declared external sources)."""
    report = analyze_export(parse_export(raw))
    report["input_file_sha256"] = hashlib.sha256(raw).hexdigest()
    return report


def render_text(report):
    """Render compact transitions without hiding unavailable observations."""
    def flag(value):
        return UNKNOWN if value is None else ("YES" if value else "NO")
    lines = ["Pose lineage: descriptive only; declared evidence, not causal proof",
             f"Cases: {report['case_denominator']}; candidate denominator: {report['candidate_denominator']}",
             f"Policy: RMSD <= {report['policy']['threshold_angstrom']} angstrom; declared validity required"]
    for case in report["cases"]:
        lines.append(f"{case['case_id']}: initial={flag(case['initial_coverage_success'])} -> "
                     f"refined={flag(case['refined_coverage_success'])}; {case['refinement_transition']}; "
                     f"Top1={flag(case['top_k_success']['1'])}, Top5={flag(case['top_k_success']['5'])}; "
                     f"selection loss={flag(case['selection_loss'])}")
        for row in case["candidates"]:
            lines.append(f"  {row['candidate_id']}: {row['initial']['status']} -> {row['refined']['status']}; "
                         f"{row['transition']}; selected rank={row['selected_rank']}; "
                         f"refined convergence={row['refined']['convergence']}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as stream:
            report = analyze_bytes(stream.read(MAX_BYTES + 1))
    except (OSError, LineageError):
        print("Invalid or unreadable bounded pose-lineage export.", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) if args.format == "json"
          else render_text(report), end="\n" if args.format == "json" else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
