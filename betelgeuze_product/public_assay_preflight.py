"""Joint label-free preflight with evidence-derived completeness; never admission.

Legacy context declarations are not rewritten. Missing identity keys do not
remove graph vertices: even an incomplete candidate can bridge a reserved group.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import uuid

from betelgeuze_product import public_assay_components as components
from betelgeuze_product import residual_evidence

SCHEMA = "public_assay_joint_preflight_v2"
POLICY = "declared_and_supported_chemical_document_keys_v1"
CHEMICAL_KEYS = frozenset({"canonical", "connectivity", "inchikey_connectivity"})
MAX_BYTES = 256 * 1024 * 1024


def checked_bytes(path, expected):
    if not components.is_sha(expected):
        raise ValueError("invalid_preflight_input_sha256")
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("preflight_input_capacity_exceeded")
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("preflight_input_sha256_mismatch")
    return data


def implementation_hashes():
    return {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for name, path in (("preflight", __file__),
                               ("components", components.__file__),
                               ("residual_evidence", residual_evidence.__file__))}


def identity_evidence(node):
    """A scaffold/source record is not a sufficient molecular identity key.

    This validates retained key kinds, not the chemistry behind their hashes.
    False declarations remain incomplete even if keys happen to be supplied.
    """
    kinds = {key[0] for key in node["keys"]}
    chemical = bool(kinds & CHEMICAL_KEYS)
    document = "document" in kinds
    return {"chemical_key_available": chemical, "document_key_available": document,
            "chemical_complete": node["chemical_identity_available"] and chemical,
            "document_complete": node["document_identity_available"] and document}


def preflight(context, candidates):
    if type(context) is not list or type(candidates) is not list or not candidates:
        raise ValueError("empty_or_invalid_candidates_or_context")
    graph = components.component_index(context + candidates)
    results = []
    for node in candidates:
        group = graph[node["node_id"]]
        evidence = identity_evidence(node)
        complete = evidence["chemical_complete"] and evidence["document_complete"]
        status = ("blocked_identity" if group["blocked"] else
                  "identity_clear_review_required" if complete else "identity_incomplete")
        results.append({"candidate_id": node["node_id"], "status": status,
            "component_id": group["component_id"], "component_nodes": group["node_count"],
            "reserved_nodes_count": len(group["reserved_nodes"]),
            "unknown_policy_nodes_count": len(group["unknown_policy_nodes"]),
            "identity_evidence": evidence,
            "training_allowed": False, "calibration_allowed": False,
            "independent_evaluation_allowed": False, "prepared": False})
    return {"schema_version": SCHEMA, "completeness_policy": POLICY,
        "scope": "all supplied candidates and frozen identity metadata; not global clearance",
        "context_nodes": len(context), "candidate_count": len(candidates), "results": results}


def _publish(path, payload):
    """Publish a fully written file exclusively; never replace prior evidence."""
    path = Path(path)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("context", "candidates"):
        parser.add_argument("--" + name, required=True, type=Path)
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError("refuse_existing_preflight_output")
    sources = implementation_hashes()
    context_raw = checked_bytes(args.context, args.context_sha256)
    candidates_raw = checked_bytes(args.candidates, args.candidates_sha256)
    if context_raw.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(context_raw)) as stream:
            decoded = stream.read(MAX_BYTES + 1)
        if len(decoded) > MAX_BYTES:
            raise ValueError("preflight_decoded_capacity_exceeded")
    else:
        decoded = context_raw
    context = [components.loads(line) for line in decoded.decode("utf-8").splitlines() if line.strip()]
    result = preflight(context, components.loads(candidates_raw.decode("utf-8")))
    if implementation_hashes() != sources:
        raise ValueError("preflight_implementation_changed")
    checked_bytes(args.context, args.context_sha256)
    checked_bytes(args.candidates, args.candidates_sha256)
    result.update(context_sha256=args.context_sha256, candidates_sha256=args.candidates_sha256,
                  implementation_sha256=sources)
    _publish(args.output, json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
