from __future__ import annotations

import json

import pytest

from tools.product import build_release_claim_evidence_ladder_gate as mod

pytest.importorskip("hypothesis")

from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

SHA = "a" * 40


def _tier_results(local: bool, remote: bool, runtime: bool) -> dict:
    return {
        mod.TIER_LOCAL: {"tier": mod.TIER_LOCAL, "rank": 1, "result": "supported" if local else "not_supported"},
        mod.TIER_REMOTE: {"tier": mod.TIER_REMOTE, "rank": 2, "result": "supported" if remote else "not_supported"},
        mod.TIER_RUNTIME: {"tier": mod.TIER_RUNTIME, "rank": 3, "result": "supported" if runtime else "not_supported"},
    }


@given(st.booleans(), st.booleans(), st.booleans())
def test_property_contiguous_and_never_overclaim(local: bool, remote: bool, runtime: bool) -> None:
    """Property 1 (never over-claim) + Property 2 (contiguity from rank 1)."""
    results = _tier_results(local, remote, runtime)
    highest, _gaps = mod._rank_ladder(results)
    if highest == mod.NONE_CLAIM:
        assert not local
    else:
        rank = mod.TIER_RANK[highest]
        for tier in mod.TIER_ORDER:
            if mod.TIER_RANK[tier] <= rank:
                assert results[tier]["result"] == "supported"
    supported_ranks = [mod.TIER_RANK[t] for t in mod.TIER_ORDER if results[t]["result"] == "supported"]
    highest_rank = 0 if highest == mod.NONE_CLAIM else mod.TIER_RANK[highest]
    assert highest_rank <= (max(supported_ranks) if supported_ranks else 0)


@given(st.booleans(), st.booleans(), st.booleans())
def test_property_runtime_claim_iff_runtime_tier(local: bool, remote: bool, runtime: bool) -> None:
    """Property 4: runtime_claim_allowed iff the runtime tier is the highest supported."""
    results = _tier_results(local, remote, runtime)
    highest, _ = mod._rank_ladder(results)
    runtime_claim_allowed = highest == mod.TIER_RUNTIME
    assert runtime_claim_allowed == (local and remote and runtime)


@settings(max_examples=50)
@given(st.text(max_size=45))
def test_property_arbitrary_sha_fail_closed_without_evidence(tmp_path_factory, sha: str) -> None:
    """Property 3 (fail-closed) + Property 9 (read-only invariance) with no evidence."""
    tmp_path = tmp_path_factory.mktemp("ladder")
    payload = mod.build_release_claim_evidence_ladder_gate(root=tmp_path, merge_commit_sha=sha)
    summary = payload["summary"]
    assert summary["highest_supported_claim"] == "none"
    assert summary["runtime_claim_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


@given(st.lists(st.sampled_from(["a" * 40, "b" * 40, "c" * 40]), max_size=6))
def test_property_attribution_exactness(shas: list[str]) -> None:
    """Property 5: only completed/success runs whose head_sha matches are attributed."""
    records = [
        {"id": i, "head_sha": sha, "status": "completed", "conclusion": "success",
         "run_completed_at": f"2026-06-{10 + i:02d}T00:00:00Z"}
        for i, sha in enumerate(shas)
    ]
    run = mod._attributed_run(records, SHA)
    if any(s == SHA for s in shas):
        assert run is not None and run["head_sha"] == SHA
    else:
        assert run is None
