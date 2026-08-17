from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load("d1_runner_hardening", ROOT / "tools/run_engine_v2_d1_development_v1.py")
VERIFIER = load("d1_verifier_hardening", ROOT / "tools/verify_engine_v2_d1_development_v1.py")


def make_case(i: int, *, rmsd: float = 4.0, best: float = 3.0) -> dict:
    recovered = rmsd <= 2.0
    return {
        "case_id": f"D1_CASE_{i:03d}",
        "preparation_success": True,
        "preparation_failure_code": None,
        "scored_candidate_count": 64,
        "typed_failure_count": 0,
        "proposal_oracle_recovered": i < 2,
        "valid_proposal_oracle_recovered": i < 2,
        "top1_recovered": recovered,
        "top5_recovered": recovered or i == 1,
        "top1_valid": False if i == 1 else True,
        "top1_lane": "uniform",
        "top1_slot_index": 0,
        "top1_final_rmsd_angstrom": rmsd,
        "best_final_rmsd_angstrom": best,
        "scoring_regret_angstrom": rmsd - best,
        "source_sha256": f"{i + 1:064x}",
    }


def make_summary() -> dict:
    cases = [make_case(0, rmsd=1.0, best=0.5), make_case(1, rmsd=3.0, best=1.0)]
    cases += [make_case(i) for i in range(2, 32)]
    regrets = [row["scoring_regret_angstrom"] for row in cases]
    return {
        "cases": cases,
        "aggregate": {
            "case_count": 32,
            "preparation_success_count": 32,
            "preparation_failure_count": 0,
            "scored_case_count": 32,
            "proposal_oracle_recovery_count": 2,
            "valid_proposal_oracle_recovery_count": 2,
            "top1_recovery_count": 1,
            "top5_recovery_count": 2,
            "invalid_top1_count": 1,
            "top1_validity_unavailable_count": 0,
            "mean_scoring_regret_angstrom": sum(regrets) / 32,
            "preparation_failure_distribution": {},
            "typed_failure_distribution": {},
            "lane_contribution": {
                "uniform": {
                    "candidate_count": 2048,
                    "scored_count": 2048,
                    "proposal_oracle_candidate_count": 2,
                    "valid_proposal_oracle_candidate_count": 2,
                    "final_native_like_candidate_count": 2,
                    "exact_valid_candidate_count": 2047,
                    "top1_case_count": 32,
                    "top5_native_like_candidate_count": 2,
                }
            },
        },
    }


def make_report() -> dict:
    value = {
        "schema_id": RUNNER.REPORT_SCHEMA_ID,
        "profile_id": RUNNER.PROFILE_ID,
        "profile_sha256": "1" * 64,
        "profile_projection_sha256": "2" * 64,
        "manifest_sha256": "3" * 64,
        "manifest_projection_sha256": "4" * 64,
        "fresh_registry_sha256": "5" * 64,
        "development_repeatable": True,
        "result_informed_iteration_allowed": True,
        "candidate_denominator": 64,
        "rmsd_threshold_angstrom": 2.0,
        "current": make_summary(),
        "baseline": None,
        "authority": {
            "reservation_authorized": False,
            "molecular_holdout_execution_authorized": False,
            "fresh_128_execution_authorized": False,
            "stage0_admission_authorized": False,
            "benchmark_claim_authorized": False,
            "scientific_claim_authorized": False,
            "product_authorized": False,
            "customer_pose_emission_authorized": False,
        },
    }
    value["report_sha256"] = RUNNER._sha256_value(value)
    return value


def reseal(value: dict) -> None:
    value.pop("report_sha256", None)
    value["report_sha256"] = RUNNER._sha256_value(value)


def save(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.mark.parametrize("bad", [None, True, 1, 1.5, [], {}])
def test_manifest_result_path_keeps_original_string_type(tmp_path: Path, bad) -> None:
    manifest = {
        "schema_id": RUNNER.MANIFEST_SCHEMA_ID,
        "profile_id": RUNNER.PROFILE_ID,
        "cases": [
            {"case_id": f"D1_CASE_{i:03d}", "result_path": bad if i == 0 else f"{i}.json"}
            for i in range(32)
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RUNNER.D1DevelopmentError, match="non-empty string"):
        RUNNER._load_manifest(path)


def test_valid_report(tmp_path: Path) -> None:
    assert VERIFIER.verify_report(save(tmp_path, make_report()))["verified"] is True


def test_resealed_count_tamper_is_rejected(tmp_path: Path) -> None:
    value = make_report()
    value["current"]["aggregate"]["top1_recovery_count"] = 2
    reseal(value)
    with pytest.raises(VERIFIER.D1ReportVerificationError, match="case-row mismatch"):
        VERIFIER.verify_report(save(tmp_path, value))


def test_resealed_regret_tamper_is_rejected(tmp_path: Path) -> None:
    value = make_report()
    value["current"]["cases"][0]["scoring_regret_angstrom"] = 0.25
    reseal(value)
    with pytest.raises(VERIFIER.D1ReportVerificationError, match="regret"):
        VERIFIER.verify_report(save(tmp_path, value))


def test_resealed_lane_denominator_is_rejected(tmp_path: Path) -> None:
    value = make_report()
    value["current"]["aggregate"]["lane_contribution"]["uniform"]["candidate_count"] = 2047
    reseal(value)
    with pytest.raises(VERIFIER.D1ReportVerificationError, match="denominator"):
        VERIFIER.verify_report(save(tmp_path, value))


def test_resealed_authority_escalation_is_rejected(tmp_path: Path) -> None:
    value = make_report()
    value["authority"]["scientific_claim_authorized"] = True
    reseal(value)
    with pytest.raises(VERIFIER.D1ReportVerificationError, match="authority"):
        VERIFIER.verify_report(save(tmp_path, value))
