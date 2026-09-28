"""Bounded, metadata-only explanations of public assay identity components.

This is a diagnostic over supplied nodes. Preflight remains the authority for
component status; no result here grants source use, preparation, or training.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
import gzip
import hashlib
import io
import json
from pathlib import Path

from betelgeuze_product import public_assay_components as components
from betelgeuze_product import public_assay_preflight as preflight_module

SCHEMA = "public_assay_typed_witness_diagnostic_v1"
POLICY = "supplied_metadata_incidence_bfs_v1"
DEFAULT_MAX_NODES = 250_000
DEFAULT_MAX_INCIDENCES = 3_000_000
DEFAULT_MAX_WITNESS_VISITS = 3_000_000
DEFAULT_MAX_DIRECT_MATCHES = 1_000_000


def _positive_limit(value):
    if type(value) is not int or value < 1:
        raise ValueError("invalid_diagnostic_resource_limit")
    return value


def _boundary(node):
    reserved, unknown = components.node_reservation_status(node)
    return (["reserved"] if node["protected"] or reserved else []) + (
        ["unknown_policy"] if unknown else []
    )


def _witness(start, nodes, by_key, *, max_visits):
    """BFS over node/key incidence, visiting each high-degree key once."""
    if _boundary(nodes[start]):
        return {
            "status": "boundary_found",
            "boundary_node_id": start,
            "boundary_reasons": _boundary(nodes[start]),
            "segments": [],
            "incidence_visits": 0,
        }
    queue = deque([start])
    predecessor = {start: None}
    seen_keys = set()
    visits = 0
    while queue:
        current = queue.popleft()
        for key in sorted({tuple(key) for key in nodes[current]["keys"]}):
            if key in seen_keys:
                continue
            seen_keys.add(key)
            for neighbor in by_key[key]:
                if visits >= max_visits:
                    return {
                        "status": "incomplete_resource_cap",
                        "incidence_visits": visits,
                        "max_incidence_visits": max_visits,
                    }
                visits += 1
                if neighbor in predecessor:
                    continue
                predecessor[neighbor] = (current, key)
                if _boundary(nodes[neighbor]):
                    segments = []
                    target = neighbor
                    while predecessor[target] is not None:
                        previous, via = predecessor[target]
                        segments.append(
                            {
                                "from_node_id": previous,
                                "key_kind": via[0],
                                "key_sha256": via[1],
                                "to_node_id": target,
                            }
                        )
                        target = previous
                    segments.reverse()
                    return {
                        "status": "boundary_found",
                        "boundary_node_id": neighbor,
                        "boundary_reasons": _boundary(nodes[neighbor]),
                        "segments": segments,
                        "incidence_visits": visits,
                    }
                queue.append(neighbor)
    return {
        "status": "no_boundary_in_supplied_graph",
        "segments": [],
        "incidence_visits": visits,
    }


def diagnostic(
    context,
    candidates,
    *,
    max_nodes=DEFAULT_MAX_NODES,
    max_incidences=DEFAULT_MAX_INCIDENCES,
    max_witness_visits=DEFAULT_MAX_WITNESS_VISITS,
    max_direct_matches=DEFAULT_MAX_DIRECT_MATCHES,
):
    """Explain exactly the supplied graph, using the existing preflight policy."""
    for limit in (max_nodes, max_incidences, max_witness_visits, max_direct_matches):
        _positive_limit(limit)
    if type(context) is not list or type(candidates) is not list or not candidates:
        raise ValueError("empty_or_invalid_candidates_or_context")
    nodes_list = context + candidates
    if len(nodes_list) > max_nodes:
        raise ValueError("diagnostic_node_capacity_exceeded")
    incidence_count = sum(
        len(node.get("keys", [])) for node in nodes_list if isinstance(node, dict)
    )
    if incidence_count > max_incidences:
        raise ValueError("diagnostic_incidence_capacity_exceeded")
    authoritative = preflight_module.preflight(context, candidates)
    nodes = {node["node_id"]: node for node in nodes_list}
    by_key = defaultdict(list)
    for node_id in sorted(nodes):
        for key in sorted({tuple(key) for key in nodes[node_id]["keys"]}):
            by_key[key].append(node_id)
    candidate_ids = {node["node_id"] for node in candidates}
    results = []
    direct_count = 0
    for result in authoritative["results"]:
        candidate_id = result["candidate_id"]
        direct = []
        by_kind = defaultdict(set)
        for key in sorted({tuple(key) for key in nodes[candidate_id]["keys"]}):
            others = [node_id for node_id in by_key[key] if node_id != candidate_id]
            if not others:
                continue
            direct_count += len(others)
            if direct_count > max_direct_matches:
                raise ValueError("diagnostic_direct_match_capacity_exceeded")
            by_kind[key[0]].update(others)
            context_ids = [nid for nid in others if nid not in candidate_ids]
            candidate_matches = [nid for nid in others if nid in candidate_ids]
            direct.append(
                {
                    "key_kind": key[0],
                    "key_sha256": key[1],
                    "context_node_count": len(context_ids),
                    "context_node_ids_sample": context_ids[:20],
                    "context_node_ids_truncated": len(context_ids) > 20,
                    "candidate_node_ids": candidate_matches,
                    "reserved_node_count": sum(
                        "reserved" in _boundary(nodes[nid]) for nid in others
                    ),
                    "unknown_policy_node_count": sum(
                        "unknown_policy" in _boundary(nodes[nid]) for nid in others
                    ),
                }
            )
        direct_by_kind = []
        for kind, ids in sorted(by_kind.items()):
            direct_by_kind.append(
                {
                    "key_kind": kind,
                    "context_node_count": len(ids - candidate_ids),
                    "candidate_node_count": len(ids & candidate_ids),
                    "reserved_node_count": sum(
                        "reserved" in _boundary(nodes[nid]) for nid in ids
                    ),
                    "unknown_policy_node_count": sum(
                        "unknown_policy" in _boundary(nodes[nid]) for nid in ids
                    ),
                }
            )
        witness = _witness(candidate_id, nodes, by_key, max_visits=max_witness_visits)
        if (
            result["status"] == "blocked_identity"
            and witness["status"] == "no_boundary_in_supplied_graph"
        ):
            raise ValueError("blocked_component_without_boundary_witness")
        results.append(
            {
                "candidate_id": candidate_id,
                "authoritative_preflight": result,
                "direct_overlaps": direct,
                "direct_summary_by_key_kind": direct_by_kind,
                "candidate_document_links": sorted(
                    by_kind.get("document", set()) & candidate_ids
                ),
                "boundary_witness": witness,
            }
        )
    return {
        "schema_version": SCHEMA,
        "diagnostic_policy": POLICY,
        "scope": "supplied metadata only; diagnostic cannot grant clearance",
        "context_nodes": len(context),
        "candidate_count": len(candidates),
        "incidence_count": incidence_count,
        "diagnostic_complete": all(
            row["boundary_witness"]["status"] != "incomplete_resource_cap"
            for row in results
        ),
        "results": results,
    }


def _read_context(data):
    if data.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            data = stream.read(preflight_module.MAX_BYTES + 1)
        if len(data) > preflight_module.MAX_BYTES:
            raise ValueError("diagnostic_decoded_capacity_exceeded")
    return [
        components.loads(line)
        for line in data.decode("utf-8").splitlines()
        if line.strip()
    ]


def _implementation_hashes():
    return {
        **preflight_module.implementation_hashes(),
        "graph_diagnostic": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("context", "candidates"):
        parser.add_argument("--" + name, required=True, type=Path)
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--preflight-sha256")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    parser.add_argument("--max-incidences", type=int, default=DEFAULT_MAX_INCIDENCES)
    parser.add_argument(
        "--max-witness-visits", type=int, default=DEFAULT_MAX_WITNESS_VISITS
    )
    parser.add_argument(
        "--max-direct-matches", type=int, default=DEFAULT_MAX_DIRECT_MATCHES
    )
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError("refuse_existing_diagnostic_output")
    if (args.preflight is None) != (args.preflight_sha256 is None):
        raise ValueError("preflight_path_and_sha256_required_together")
    hashes = _implementation_hashes()
    context_raw = preflight_module.checked_bytes(args.context, args.context_sha256)
    candidates_raw = preflight_module.checked_bytes(
        args.candidates, args.candidates_sha256
    )
    context = _read_context(context_raw)
    candidates = components.loads(candidates_raw.decode("utf-8"))
    report = diagnostic(
        context,
        candidates,
        max_nodes=args.max_nodes,
        max_incidences=args.max_incidences,
        max_witness_visits=args.max_witness_visits,
        max_direct_matches=args.max_direct_matches,
    )
    expected_preflight = preflight_module.preflight(context, candidates)
    expected_preflight.update(
        context_sha256=args.context_sha256,
        candidates_sha256=args.candidates_sha256,
        implementation_sha256=preflight_module.implementation_hashes(),
    )
    if args.preflight is not None:
        observed = components.loads(
            preflight_module.checked_bytes(
                args.preflight, args.preflight_sha256
            ).decode("utf-8")
        )
        if observed != expected_preflight:
            raise ValueError("authoritative_preflight_mismatch")
    if _implementation_hashes() != hashes:
        raise ValueError("diagnostic_implementation_changed")
    preflight_module.checked_bytes(args.context, args.context_sha256)
    preflight_module.checked_bytes(args.candidates, args.candidates_sha256)
    if args.preflight is not None:
        preflight_module.checked_bytes(args.preflight, args.preflight_sha256)
    report.update(
        context_sha256=args.context_sha256,
        candidates_sha256=args.candidates_sha256,
        preflight_sha256=args.preflight_sha256,
        authoritative_preflight_policy=preflight_module.POLICY,
        authoritative_preflight_schema=preflight_module.SCHEMA,
        implementation_sha256=hashes,
    )
    preflight_module._publish(
        args.output,
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
