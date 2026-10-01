"""Exact streaming rank summaries for prespecified arm pairs on one cohort.

No label loading or admission. The caller must freeze scope, predictions and
comparisons first. Missing outcomes/scores remain in full-pool denominators.
Chunked details are optional; summaries never store an O(N**2) pair list.
"""
from __future__ import annotations

from hashlib import sha256
from itertools import combinations
import json

from .censored_rank_metrics import _endpoint, _number, endpoint_order

SCHEMA = "paired_concentration_rank_summary_v1"
STATUSES = ("concordant", "discordant", "score_tie", "endpoint_tie",
            "endpoint_order_unknown", "score_missing", "endpoint_missing")


def _encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _status(truth, missing_endpoint, a, b, values):
    if missing_endpoint:
        return "endpoint_missing"
    if truth is None:
        return "endpoint_order_unknown"
    if truth == 0:
        return "endpoint_tie"
    if a not in values or b not in values:
        return "score_missing"
    if values[a] == values[b]:
        return "score_tie"
    return "concordant" if (values[a] > values[b]) == (truth < 0) else "discordant"


def _finish(ids, endpoints, values, counts, comparable_digest):
    n = sum(counts[k] for k in ("concordant", "discordant", "score_tie"))
    return {"candidate_denominator": len(ids), "scores_available": len(values),
            "endpoints_available": sum(endpoints[rid] is not None for rid in ids),
            "all_pairs": sum(counts.values()), "known_endpoint_pairs": n + counts["score_missing"],
            "scored_comparable_pairs": n, "counts": counts,
            "scored_pair_ids_sha256": comparable_digest.hexdigest(),
            "concordance": (counts["concordant"] + .5 * counts["score_tie"]) / n if n else None}


def _prepare_cohort(endpoints, arms, comparisons, max_pair_work):
    """Validate and snapshot candidate inputs; never enumerate pairs."""
    if type(endpoints) is not dict or not 1 <= len(endpoints) <= 10000:
        raise ValueError("invalid_rank_cohort")
    if any(type(rid) is not str or not rid for rid in endpoints):
        raise ValueError("nonempty_rank_candidate_ids_required")
    if type(arms) is not dict or not 1 <= len(arms) <= 32:
        raise ValueError("invalid_rank_arms")
    if type(max_pair_work) is not int or not 1 <= max_pair_work <= 100_000_000:
        raise ValueError("invalid_rank_work_limit")
    ids = sorted(endpoints)
    # Snapshot inputs so caller/sink mutation cannot alter the in-progress metric.
    outcomes = {}
    for rid, endpoint in endpoints.items():
        if endpoint is not None:
            if type(endpoint) is not dict:
                raise ValueError("invalid_rank_endpoint")
            _endpoint(endpoint)
        outcomes[rid] = None if endpoint is None else dict(endpoint)
    values = {}
    for arm, scores in arms.items():
        if type(arm) is not str or not arm or type(scores) is not dict or set(scores) - set(ids):
            raise ValueError("invalid_rank_score_ids")
        values[arm] = {rid: _number(value) for rid, value in scores.items() if value is not None}
    if type(comparisons) is not list or len(comparisons) > 64:
        raise ValueError("explicit_bounded_arm_comparisons_required")
    pairs, seen = [], set()
    for pair in comparisons:
        if (type(pair) is not list or len(pair) != 2 or any(type(x) is not str for x in pair)
                or pair[0] == pair[1] or any(x not in values for x in pair)):
            raise ValueError("invalid_arm_comparison")
        key = tuple(sorted(pair))
        if key in seen:
            raise ValueError("duplicate_arm_comparison")
        seen.add(key)
        pairs.append(tuple(pair))
    work = len(ids) * (len(ids) - 1) // 2 * (len(values) + 2 * len(pairs))
    if work > max_pair_work:
        raise ValueError("rank_pair_work_limit_exceeded")
    return ids, outcomes, values, pairs, work


def validate_cohort(endpoints, arms, comparisons, *, max_pair_work=5_000_000):
    """Use identical admission and arithmetic work bounds without running a metric."""
    ids, _, values, pairs, work = _prepare_cohort(endpoints, arms, comparisons, max_pair_work)
    return {"candidate_denominator": len(ids), "arm_count": len(values),
            "comparison_count": len(pairs), "pair_arm_work_reserved": work}


def compare_cohort(endpoints, arms, comparisons, *, max_pair_work=5_000_000,
                   detail_sink=None, chunk_size=1024):
    """Compare full coverage and common candidate/pair coverage simultaneously.

    Scores must already be higher-is-better. Endpoints are positive exact '=' or
    strict '>' concentrations in one unit; None preserves unavailable outcomes.
    `comparisons` is an explicit list of two arm names per requested comparison.
    A sink receives ordered chunks, must persist them itself, and may raise to
    abort. No result is returned after a sink failure. No intervals/significance,
    equal runtime, independence or AI advantage are inferred here.
    """
    if type(chunk_size) is not int or not 1 <= chunk_size <= 4096:
        raise ValueError("invalid_rank_chunk_size")
    if detail_sink is not None and not callable(detail_sink):
        raise ValueError("rank_detail_sink_must_be_callable")
    ids, outcomes, values, pairs, work = _prepare_cohort(endpoints, arms, comparisons, max_pair_work)
    counts = {arm: dict.fromkeys(STATUSES, 0) for arm in values}
    digests = {arm: sha256() for arm in values}
    common = [sorted(set(values[a]) & set(values[b])) for a, b in pairs]
    common_sets = [set(group) for group in common]
    common_counts = [{arm: dict.fromkeys(STATUSES, 0) for arm in pair} for pair in pairs]
    common_digests = [{arm: sha256() for arm in pair} for pair in pairs]
    # Encode each ID once; framed pair bytes are identical to canonical [a,b] JSON.
    encoded_ids = {rid: json.dumps(rid, ensure_ascii=True).encode() for rid in ids}
    detail_hash, chunk, detail_count = sha256(), [], 0
    for left, right in combinations(ids, 2):
        absent = outcomes[left] is None or outcomes[right] is None
        truth = None if absent else endpoint_order(outcomes[left], outcomes[right])
        statuses = {arm: _status(truth, absent, left, right, scores) for arm, scores in values.items()}
        pair_bytes = b"[" + encoded_ids[left] + b"," + encoded_ids[right] + b"]\n"
        for arm, status in statuses.items():
            counts[arm][status] += 1
            if status in {"concordant", "discordant", "score_tie"}:
                digests[arm].update(pair_bytes)
        for index, pair in enumerate(pairs):
            if left in common_sets[index] and right in common_sets[index]:
                for arm in pair:
                    status = statuses[arm]
                    common_counts[index][arm][status] += 1
                    if status in {"concordant", "discordant", "score_tie"}:
                        common_digests[index][arm].update(pair_bytes)
        if detail_sink is not None:
            row = {"left": left, "right": right, "known_order": truth,
                   "endpoint_missing": absent, "status_by_arm": statuses}
            detail_hash.update(_encoded(row))
            detail_count += 1
            chunk.append(row)
            if len(chunk) == chunk_size:
                detail_sink(chunk)
                chunk = []
    if chunk:
        detail_sink(chunk)
    full = {arm: _finish(ids, outcomes, scores, counts[arm], digests[arm]) for arm, scores in values.items()}
    matched = []
    for index, (a, b) in enumerate(pairs):
        group = common[index]
        summaries = {arm: _finish(group, outcomes, {rid: values[arm][rid] for rid in group},
                      common_counts[index][arm], common_digests[index][arm]) for arm in (a, b)}
        first, second = summaries[a], summaries[b]
        if first["scored_pair_ids_sha256"] != second["scored_pair_ids_sha256"]:
            raise RuntimeError("internal_common_pair_identity_mismatch")
        ca, cb = first["concordance"], second["concordance"]
        matched.append({"arms": [a, b], "full_candidate_denominator": len(ids),
            "common_candidate_ids": group, "common_candidate_ids_sha256": sha256(_encoded(group)).hexdigest(),
            "same_available_candidate_ids": set(values[a]) == set(values[b]),
            "common_candidate_fraction": len(group) / len(ids), "metrics": summaries,
            "second_minus_first_on_common_pairs": None if ca is None else cb - ca})
    return {"schema_version": SCHEMA, "cohort_ids_sha256": sha256(_encoded(ids)).hexdigest(),
            "candidate_denominator": len(ids), "pair_arm_work_reserved": work,
            "full_coverage": full, "common_coverage": matched,
            "detail_rows": detail_count, "detail_sha256": detail_hash.hexdigest() if detail_sink else None,
            "details_streamed": detail_sink is not None, "scientifically_validated": False,
            "ai_advantage_claimed": False, "confidence_intervals_computed": False}
