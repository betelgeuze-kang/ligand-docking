from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load(
    "run_engine_v2_d1_development_v1",
    ROOT / "tools/run_engine_v2_d1_development_v1.py",
)
VERIFIER = _load(
    "verify_engine_v2_d1_development_v1",
    ROOT / "tools/verify_engine_v2_d1_development_v1.py",
)


def _candidate(
    slot: int,
    *,
    lane: str = "uniform",
    score: float | None = None,
    proposal_rmsd: float = 4.0,
    final_rmsd: float = 4.0,
    proposal_valid: bool | None = True,
    pose_valid: bool | None = True,
    failure_code: str | None = None,
) -> dict[str, object]:
    if failure_code is not None:
        return {
            "slot_index": slot,
            "lane": lane,
            "status": "typed_failure",
            "failure_code": failure_code,
            "score": None,
            "proposal_rmsd_angstrom": None,
            "final_rmsd_angstrom": None,
            "proposal_valid": None,
            "pose_valid": None,
        }
    return {
        "slot_index": slot,
        "lane": lane,
        "status": "scored",
        "failure_code": None,
        "score": float(slot if score is None else score),
        "proposal_rmsd_angstrom": proposal_rmsd,
        "final_rmsd_angstrom": final_rmsd,
        "proposal_valid": proposal_valid,
        "pose_valid": pose_valid,
    }


def _build_inputs(tmp_path: Path, *, baseline: bool = False) -> tuple[Path, Path, Path]:
    root = tmp_path / ("baseline" if baseline else "current")
    root.mkdir()
    rows = []
    for case_index in range(RUNNER.CASE_COUNT):
        case_id = f"D1_CASE_{case_index:03d}"
        candidates = [_candidate(slot, lane="uniform" if slot < 32 else "guided") for slot in range(64)]
        if case_index == 0:
            candidates[0] = _candidate(
                0,
                score=0.0,
                proposal_rmsd=1.0,
                final_rmsd=3.0 if baseline else 1.0,
                proposal_valid=True,
                pose_valid=True,
            )
        if case_index == 1:
            candidates[0] = _candidate(
                0,
                score=0.0,
                proposal_rmsd=1.2,
                final_rmsd=1.2 if baseline else 3.2,
                proposal_valid=True,
                pose_valid=False,
            )
        if case_index == 2:
            candidates[4] = _candidate(
                4,
                score=4.0,
                proposal_rmsd=1.5,
                final_rmsd=1.5,
                proposal_valid=True,
                pose_valid=True,
            )
        if case_index == 3:
            candidates[63] = _candidate(63, lane="guided", failure_code="source_missing")
        result = {
            "schema_id": RUNNER.CASE_RESULT_SCHEMA_ID,
            "case_id": case_id,
            "preparation_status": "success",
            "preparation_failure_code": None,
            "candidate_denominator": RUNNER.CANDIDATE_DENOMINATOR,
            "candidates": candidates,
        }
        result_name = f"{case_id}.json"
        (root / result_name).write_text(json.dumps(result), encoding="utf-8")
        rows.append({"case_id": case_id, "result_path": result_name})

    manifest = {
        "schema_id": RUNNER.MANIFEST_SCHEMA_ID,
        "profile_id": RUNNER.PROFILE_ID,
        "cases": rows,
    }
    manifest_path = tmp_path / ("baseline-manifest.json" if baseline else "manifest.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    fresh = {
        "schema_id": RUNNER.FRESH_REGISTRY_SCHEMA_ID,
        "case_ids": [f"FRESH_{index:03d}" for index in range(RUNNER.FRESH_CASE_COUNT)],
    }
    fresh_path = tmp_path / "fresh.json"
    fresh_path.write_text(json.dumps(fresh), encoding="utf-8")
    return manifest_path, root, fresh_path


def test_builds_repeatable_scorecard_and_verifies(tmp_path: Path) -> None:
    manifest, result_root, fresh = _build_inputs(tmp_path)
    report = RUNNER.build_report(
        profile_path=ROOT / "config/engine_v2_d1_development_profile_v1.json",
        manifest_path=manifest,
        fresh_registry_path=fresh,
        result_root=result_root,
    )
    aggregate = report["current"]["aggregate"]
    assert aggregate["case_count"] == 32
    assert aggregate["proposal_oracle_recovery_count"] == 3
    assert aggregate["valid_proposal_oracle_recovery_count"] == 3
    assert aggregate["top1_recovery_count"] == 1
    assert aggregate["top5_recovery_count"] == 2
    assert aggregate["invalid_top1_count"] == 1
    assert aggregate["typed_failure_distribution"] == {"source_missing": 1}
    assert report["authority"]["scientific_claim_authorized"] is False

    output = tmp_path / "report.json"
    output.write_text(json.dumps(report), encoding="utf-8")
    verified = VERIFIER.verify_report(output)
    assert verified["verified"] is True
    assert verified["authority_granted"] is False


def test_baseline_reports_new_and_lost_recovery(tmp_path: Path) -> None:
    current_manifest, current_root, fresh = _build_inputs(tmp_path)
    baseline_manifest, baseline_root, _ = _build_inputs(tmp_path, baseline=True)
    report = RUNNER.build_report(
        profile_path=ROOT / "config/engine_v2_d1_development_profile_v1.json",
        manifest_path=current_manifest,
        fresh_registry_path=fresh,
        result_root=current_root,
        baseline_manifest_path=baseline_manifest,
        baseline_result_root=baseline_root,
    )
    comparison = report["baseline"]["comparison"]
    assert comparison["new_top1_recovered_case_ids"] == ["D1_CASE_000"]
    assert comparison["lost_top1_recovered_case_ids"] == ["D1_CASE_001"]


def test_fresh_overlap_is_rejected(tmp_path: Path) -> None:
    manifest, result_root, fresh = _build_inputs(tmp_path)
    fresh_document = json.loads(fresh.read_text(encoding="utf-8"))
    fresh_document["case_ids"][0] = "D1_CASE_000"
    fresh.write_text(json.dumps(fresh_document), encoding="utf-8")
    with pytest.raises(RUNNER.D1DevelopmentError, match="overlaps"):
        RUNNER.build_report(
            profile_path=ROOT / "config/engine_v2_d1_development_profile_v1.json",
            manifest_path=manifest,
            fresh_registry_path=fresh,
            result_root=result_root,
        )


def test_incomplete_candidate_denominator_is_rejected(tmp_path: Path) -> None:
    manifest, result_root, fresh = _build_inputs(tmp_path)
    result_path = result_root / "D1_CASE_000.json"
    document = json.loads(result_path.read_text(encoding="utf-8"))
    document["candidates"].pop()
    result_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(RUNNER.D1DevelopmentError, match="all 64 candidate rows"):
        RUNNER.build_report(
            profile_path=ROOT / "config/engine_v2_d1_development_profile_v1.json",
            manifest_path=manifest,
            fresh_registry_path=fresh,
            result_root=result_root,
        )


def test_result_path_traversal_is_rejected(tmp_path: Path) -> None:
    manifest, result_root, fresh = _build_inputs(tmp_path)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["cases"][0]["result_path"] = "../outside.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(RUNNER.D1DevelopmentError, match="remain under"):
        RUNNER.build_report(
            profile_path=ROOT / "config/engine_v2_d1_development_profile_v1.json",
            manifest_path=manifest,
            fresh_registry_path=fresh,
            result_root=result_root,
        )


def test_authority_escalation_breaks_profile(tmp_path: Path) -> None:
    profile = json.loads(
        (ROOT / "config/engine_v2_d1_development_profile_v1.json").read_text(
            encoding="utf-8"
        )
    )
    profile["authority"]["scientific_claim_authorized"] = True
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(RUNNER.D1DevelopmentError, match="authority"):
        RUNNER._verify_profile(path)
