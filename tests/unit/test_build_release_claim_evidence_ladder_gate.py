from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.product import build_release_claim_evidence_ladder_gate as mod

SHA = "a" * 40
OTHER_SHA = "b" * 40


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _runs(*records: dict) -> dict:
    return {"workflow_runs": list(records)}


def _success_run(sha: str, run_id: int, completed_at: str) -> dict:
    return {
        "id": run_id,
        "head_sha": sha,
        "status": "completed",
        "conclusion": "success",
        "run_completed_at": completed_at,
    }


def _patch_receipt(monkeypatch: pytest.MonkeyPatch, *, passes: bool) -> None:
    def fake(*, root, **_inputs):  # noqa: ANN001
        status = "release_ci_remote_green_ready" if passes else "blocked_release_ci_remote_green"
        return {"summary": {"status": status, "pass": passes}, "rows": [], "blockers": []}

    monkeypatch.setattr(mod, "build_release_ci_remote_green_receipt", fake)


# --- Task 8: example-based tests --------------------------------------------------------


def test_missing_all_evidence_is_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_receipt(monkeypatch, passes=False)
    payload = mod.build_release_claim_evidence_ladder_gate(root=tmp_path, merge_commit_sha=SHA)
    summary = payload["summary"]
    assert summary["highest_supported_claim"] == "none"
    assert summary["runtime_claim_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert summary["status"] == "blocked_release_claim_evidence_ladder"


def test_local_only_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_receipt(monkeypatch, passes=False)
    local = _write(tmp_path / "local.json", {"pass": True})
    payload = mod.build_release_claim_evidence_ladder_gate(
        root=tmp_path, merge_commit_sha=SHA, local_evidence_json=local
    )
    assert payload["summary"]["highest_supported_claim"] == "local_observed_green"
    assert payload["summary"]["runtime_claim_allowed"] is False


def test_remote_supported_with_attributed_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_receipt(monkeypatch, passes=True)
    local = _write(tmp_path / "local.json", {"pass": True})
    remote = _write(tmp_path / "remote.json", _runs(_success_run(SHA, 11, "2026-06-20T00:00:00Z")))
    payload = mod.build_release_claim_evidence_ladder_gate(
        root=tmp_path, merge_commit_sha=SHA, local_evidence_json=local, remote_runs_json=remote
    )
    summary = payload["summary"]
    assert summary["remote_green_supported"] is True
    assert summary["highest_supported_claim"] == "remote_green"
    remote_tier = next(t for t in payload["tiers"] if t["tier"] == "remote_green")
    assert remote_tier["workflow_run_id"] == 11
    assert remote_tier["head_sha"] == SHA


def test_remote_pass_but_unattributed_is_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_receipt(monkeypatch, passes=True)
    local = _write(tmp_path / "local.json", {"pass": True})
    # Run is green but for a different commit -> unattributed (the PR #18 gap).
    remote = _write(tmp_path / "remote.json", _runs(_success_run(OTHER_SHA, 12, "2026-06-20T00:00:00Z")))
    payload = mod.build_release_claim_evidence_ladder_gate(
        root=tmp_path, merge_commit_sha=SHA, local_evidence_json=local, remote_runs_json=remote
    )
    remote_tier = next(t for t in payload["tiers"] if t["tier"] == "remote_green")
    assert remote_tier["result"] == "not_supported"
    assert remote_tier["block_reason"] == "unattributed"
    assert payload["summary"]["highest_supported_claim"] == "local_observed_green"


def test_runtime_supported_allows_runtime_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_receipt(monkeypatch, passes=True)
    local = _write(tmp_path / "local.json", {"pass": True})
    remote = _write(tmp_path / "remote.json", _runs(_success_run(SHA, 11, "2026-06-20T00:00:00Z")))
    runtime = _write(tmp_path / "runtime.json", _runs(_success_run(SHA, 21, "2026-06-21T00:00:00Z")))
    payload = mod.build_release_claim_evidence_ladder_gate(
        root=tmp_path, merge_commit_sha=SHA, local_evidence_json=local,
        remote_runs_json=remote, runtime_runs_json=runtime,
    )
    summary = payload["summary"]
    assert summary["highest_supported_claim"] == "runtime_green"
    assert summary["runtime_claim_allowed"] is True
    assert summary["status"] == "release_claim_evidence_ladder_ready"


def test_contiguity_runtime_supported_remote_not(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_receipt(monkeypatch, passes=True)
    local = _write(tmp_path / "local.json", {"pass": True})
    # remote unattributed, runtime attributed -> highest stays local, runtime not claimable.
    remote = _write(tmp_path / "remote.json", _runs(_success_run(OTHER_SHA, 12, "2026-06-20T00:00:00Z")))
    runtime = _write(tmp_path / "runtime.json", _runs(_success_run(SHA, 21, "2026-06-21T00:00:00Z")))
    payload = mod.build_release_claim_evidence_ladder_gate(
        root=tmp_path, merge_commit_sha=SHA, local_evidence_json=local,
        remote_runs_json=remote, runtime_runs_json=runtime,
    )
    summary = payload["summary"]
    assert summary["highest_supported_claim"] == "local_observed_green"
    assert summary["runtime_claim_allowed"] is False
    assert summary["contiguity_gap_count"] >= 1


def test_mismatched_head_sha_excluded_multiple_matches_pick_latest(tmp_path: Path) -> None:
    records = [
        _success_run(OTHER_SHA, 1, "2026-06-25T00:00:00Z"),  # mismatch excluded
        _success_run(SHA, 2, "2026-06-20T00:00:00Z"),
        _success_run(SHA, 3, "2026-06-24T00:00:00Z"),  # latest match
    ]
    run = mod._attributed_run(records, SHA)
    assert run is not None and run["id"] == 3


def test_invalid_merge_commit_sha_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_receipt(monkeypatch, passes=True)
    runtime = _write(tmp_path / "runtime.json", _runs(_success_run(SHA, 21, "2026-06-21T00:00:00Z")))
    payload = mod.build_release_claim_evidence_ladder_gate(
        root=tmp_path, merge_commit_sha="not-a-sha", runtime_runs_json=runtime
    )
    runtime_tier = next(t for t in payload["tiers"] if t["tier"] == "runtime_green")
    assert runtime_tier["result"] == "not_supported"
    assert runtime_tier["block_reason"] == "invalid_merge_commit_sha"


def test_writes_artifacts_deterministically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_receipt(monkeypatch, passes=False)
    payload = mod.build_release_claim_evidence_ladder_gate(root=tmp_path, merge_commit_sha=SHA)
    mod.write_outputs(payload, root=tmp_path)
    json_path = tmp_path / mod.DEFAULT_OUT_JSON
    first = json_path.read_bytes()
    mod.write_outputs(payload, root=tmp_path)
    assert json_path.read_bytes() == first  # byte-identical
    assert (tmp_path / mod.DEFAULT_OUT_CSV).is_file()
    assert (tmp_path / mod.DEFAULT_OUT_MD).is_file()


def test_round_trip_and_read_only_invariance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_receipt(monkeypatch, passes=False)
    payload = mod.build_release_claim_evidence_ladder_gate(root=tmp_path, merge_commit_sha=SHA)
    serialized = json.dumps(payload, sort_keys=True)
    assert json.loads(serialized) == payload  # Property 7: round-trip fidelity
    assert payload["summary"]["execution_enabled"] is False  # Property 9
    assert payload["summary"]["external_state_mutated"] is False
