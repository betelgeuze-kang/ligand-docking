"""Independent expected counts, legacy parity, streaming bounds and matched sets."""
from copy import deepcopy
from hashlib import sha256
import json
import random

import pytest

from betelgeuze_engine.product.censored_rank_metrics import compare_rankings
from betelgeuze_engine.product.paired_rank_metrics import compare_cohort


def ep(value, relation="="):
    return {"value": value, "relation": relation}


@pytest.mark.parametrize("seed", range(30))
def test_legacy_full_counts_are_exact(seed):
    rng = random.Random(seed)
    outcomes = {str(i): ep(rng.randint(1, 10), rng.choice(["=", ">"])) for i in range(16)}
    arms = {name: {rid: rng.choice([None, 0., 1., 2.]) for rid in outcomes} for name in ("a", "b", "c")}
    before = deepcopy((outcomes, arms))
    old = compare_rankings(outcomes, arms)
    new = compare_cohort(outcomes, arms, [["a", "b"], ["a", "c"]])
    for arm in arms:
        summary = new["full_coverage"][arm]
        counts = dict(summary["counts"])
        assert counts.pop("endpoint_missing") == 0
        assert counts == old[arm]["counts"]
        for key in ("candidate_denominator", "scores_available", "all_pairs", "known_endpoint_pairs", "scored_comparable_pairs", "concordance"):
            assert summary[key] == old[arm][key]
    assert (outcomes, arms) == before


def test_equal_counts_are_not_equal_candidates():
    outcomes = {rid: ep(i + 1) for i, rid in enumerate("abcd")}
    arms = {"a": {"a": 0, "b": 2, "c": 1}, "b": {"b": 3, "c": 2, "d": 1}}
    report = compare_cohort(outcomes, arms, [["a", "b"]])
    assert report["full_coverage"]["a"]["concordance"] == 1/3
    assert report["full_coverage"]["b"]["concordance"] == 1
    matched = report["common_coverage"][0]
    assert matched["common_candidate_ids"] == ["b", "c"]
    assert not matched["same_available_candidate_ids"]
    assert matched["second_minus_first_on_common_pairs"] == 0
    assert matched["metrics"]["a"]["scored_pair_ids_sha256"] == matched["metrics"]["b"]["scored_pair_ids_sha256"]


def test_missing_endpoints_and_no_common_pairs_do_not_impute():
    report = compare_cohort({"a": ep(1), "b": ep(2, ">"), "c": None}, {"a": {"a": 2}, "b": {}}, [["a", "b"]])
    assert report["full_coverage"]["a"]["candidate_denominator"] == 3
    assert report["full_coverage"]["a"]["counts"]["endpoint_missing"] == 2
    assert report["common_coverage"][0]["metrics"]["a"]["concordance"] is None
    assert report["common_coverage"][0]["second_minus_first_on_common_pairs"] is None


@pytest.mark.parametrize("chunk_size", [1, 7, 32, 4096])
def test_streamed_details_preserve_hash_and_bound_memory(chunk_size):
    endpoints = {str(i): ep(i + 1) for i in range(20)}
    scores = {"a": {rid: -i for i, rid in enumerate(endpoints)}, "b": {}}
    emitted, sizes = [], []
    def sink(rows):
        sizes.append(len(rows))
        emitted.extend(rows)
    report = compare_cohort(endpoints, scores, [["a", "b"]], detail_sink=sink, chunk_size=chunk_size)
    raw = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in emitted).encode()
    assert max(sizes) <= chunk_size
    assert len(emitted) == 190
    assert sha256(raw).hexdigest() == report["detail_sha256"]
    summary = compare_cohort(endpoints, scores, [["a", "b"]])
    assert summary["full_coverage"] == report["full_coverage"]
    assert summary["common_coverage"] == report["common_coverage"]
    assert not summary["details_streamed"] and summary["detail_rows"] == 0


def test_sink_failure_aborts():
    def fail(rows):
        raise OSError("simulated full disk")
    with pytest.raises(OSError, match="full disk"):
        compare_cohort({"a": ep(1), "b": ep(2)}, {"arm": {}}, [], detail_sink=fail)


def test_sink_mutation_cannot_change_computation():
    outcomes = {str(i): ep(i + 1) for i in range(4)}
    arms = {"arm": {rid: -i for i, rid in enumerate(outcomes)}}
    expected = compare_cohort(outcomes, arms, [])
    def mutate(rows):
        outcomes.clear()
        arms.clear()
    actual = compare_cohort(outcomes, arms, [], detail_sink=mutate, chunk_size=1)
    assert expected["full_coverage"] == actual["full_coverage"]


@pytest.mark.parametrize("change", ["id", "unknown_score", "bool_score", "nan", "bad_endpoint", "duplicate", "missing_arm", "same_arm", "bool_limit", "limit", "chunk"])
def test_invalid_or_unbounded_inputs_rejected(change):
    endpoints, arms, pairs, kwargs = {"a": ep(1), "b": ep(2)}, {"x": {}, "y": {}}, [["x", "y"]], {}
    if change == "id":
        endpoints[1] = ep(3)
    elif change == "unknown_score":
        arms["x"]["z"] = 1
    elif change == "bool_score":
        arms["x"]["a"] = True
    elif change == "nan":
        arms["x"]["a"] = float("nan")
    elif change == "bad_endpoint":
        endpoints["a"] = ep(2, ">=")
    elif change == "duplicate":
        pairs += [["y", "x"]]
    elif change == "missing_arm":
        pairs = [["x", "z"]]
    elif change == "same_arm":
        pairs = [["x", "x"]]
    elif change == "bool_limit":
        kwargs["max_pair_work"] = True
    elif change == "limit":
        kwargs["max_pair_work"] = 1
    else:
        kwargs["chunk_size"] = 0
    with pytest.raises(ValueError):
        compare_cohort(endpoints, arms, pairs, **kwargs)
