"""Joint, label-free candidate preflight; never a data-admission decision."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from tools.product import public_assay_components as components


def checked_bytes(path, expected):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("preflight_input_sha256_mismatch")
    return data


def preflight(context, candidates):
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("empty_or_invalid_candidates")
    # Include all candidates before filtering or assigning roles. One candidate
    # can bridge another candidate into reserved context.
    graph = components.component_index(context + candidates)
    results = []
    for node in candidates:
        group = graph[node["node_id"]]
        complete = node["chemical_identity_available"] and node["document_identity_available"]
        status = ("blocked_identity" if group["blocked"] else
                  "identity_clear_review_required" if complete else "identity_incomplete")
        results.append({
            "candidate_id": node["node_id"], "status": status,
            "component_id": group["component_id"],
            "component_nodes": group["node_count"],
            "reserved_nodes_count": len(group["reserved_nodes"]),
            "unknown_policy_nodes_count": len(group["unknown_policy_nodes"]),
            "training_allowed": False, "calibration_allowed": False,
            "independent_evaluation_allowed": False, "prepared": False,
        })
    return {
        "schema_version": "public_assay_joint_preflight_v1",
        "scope": "all supplied candidates and frozen identity metadata; not global clearance",
        "context_nodes": len(context), "candidate_count": len(candidates),
        "results": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", required=True, type=Path)
    parser.add_argument("--context-sha256", required=True)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--candidates-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError("refuse_existing_preflight_output")
    context_raw = checked_bytes(args.context, args.context_sha256)
    candidates_raw = checked_bytes(args.candidates, args.candidates_sha256)
    decoded = gzip.decompress(context_raw) if context_raw.startswith(b"\x1f\x8b") else context_raw
    context = [components.loads(line) for line in decoded.decode("utf-8").splitlines() if line.strip()]
    result = preflight(context, components.loads(candidates_raw.decode("utf-8")))
    result.update(context_sha256=args.context_sha256, candidates_sha256=args.candidates_sha256)
    result["implementation_sha256"] = {
        name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for name, path in (("preflight", __file__), ("components", components.__file__))
    }
    payload = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
