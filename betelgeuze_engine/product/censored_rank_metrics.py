"""Post-admission descriptive ranks; does not authorize label access or fitting.

Callers must freeze predictions and enforce source/role boundaries before passing
endpoints. All endpoints must belong to one target/domain/assay/endpoint/unit.
Reported point estimates are not uncertainty intervals or binary activity labels.
"""
from itertools import combinations
from math import isfinite


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("values must be finite numbers")
    return value


def _endpoint(value):
    if set(value) != {"relation", "value"} or value["relation"] not in {"=", ">"}:
        raise ValueError("only exact and strictly right-censored endpoints are supported")
    if _number(value["value"]) <= 0:
        raise ValueError("concentration must be positive")


def endpoint_order(left, right):
    """Return -1/0/1 for known concentration order, or None if unresolved."""
    _endpoint(left)
    _endpoint(right)
    a, b = left["value"], right["value"]
    ra, rb = left["relation"], right["relation"]
    if ra == rb == "=":
        return (a > b) - (a < b)
    if ra == "=" and rb == ">" and a <= b:
        return -1
    if ra == ">" and rb == "=" and a >= b:
        return 1
    return None


def compare_rankings(endpoints, arms):
    """Retain the full cohort; each arm maps IDs to higher-is-better scores.

    Missing IDs or None scores remain unscored. Concordance describes only the
    explicitly counted scored pairs, and must not compare unequal coverage.
    """
    if any(not isinstance(key, str) or not key for key in endpoints):
        raise ValueError("candidate IDs must be nonempty strings")
    for endpoint in endpoints.values():
        _endpoint(endpoint)
    output = {}
    for arm, scores in arms.items():
        if set(scores) - set(endpoints):
            raise ValueError("score IDs outside the fixed cohort")
        available = {key: _number(value) for key, value in scores.items() if value is not None}
        counts = dict(concordant=0, discordant=0, score_tie=0,
                      endpoint_tie=0, endpoint_order_unknown=0, score_missing=0)
        pairs = []
        for a, b in combinations(sorted(endpoints), 2):
            truth = endpoint_order(endpoints[a], endpoints[b])
            if truth is None:
                status = "endpoint_order_unknown"
            elif truth == 0:
                status = "endpoint_tie"
            elif a not in available or b not in available:
                status = "score_missing"
            elif available[a] == available[b]:
                status = "score_tie"
            else:
                status = "concordant" if (available[a] > available[b]) == (truth < 0) else "discordant"
            counts[status] += 1
            pairs.append(dict(left=a, right=b, known_order=truth, status=status))
        n = sum(counts[k] for k in ("concordant", "discordant", "score_tie"))
        output[arm] = dict(candidate_denominator=len(endpoints), scores_available=len(available),
                           all_pairs=len(pairs), known_endpoint_pairs=n + counts["score_missing"],
                           scored_comparable_pairs=n, counts=counts, pairs=pairs,
                           concordance=(counts["concordant"] + .5 * counts["score_tie"]) / n if n else None)
    return output
