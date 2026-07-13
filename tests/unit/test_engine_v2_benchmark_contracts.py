from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkContractError,
    BenchmarkManifest,
    BenchmarkRunContext,
    MetricAggregation,
    MetricDefinition,
    MetricDirection,
    benchmark_case_seed,
    run_benchmark_manifest,
    verify_signed_benchmark_report,
)


def _definition() -> MetricDefinition:
    return MetricDefinition(
        metric_id="pose_rmsd_angstrom",
        unit="angstrom",
        direction=MetricDirection.MINIMIZE,
        valid_min=0.0,
        valid_max=100.0,
        pass_threshold=2.0,
        aggregation=MetricAggregation.MEAN,
        confidence_level=0.90,
        bootstrap_samples=200,
    )


def _cases() -> tuple[BenchmarkCase, ...]:
    return tuple(
        BenchmarkCase(
            case_id=f"case-{index}",
            input_sha256=str(index + 1) * 64,
            task="pose_rmsd",
            target_id=f"T{index}",
            ligand_id=f"L{index}",
        )
        for index in range(3)
    )


def _manifest(cases=None) -> BenchmarkManifest:
    return BenchmarkManifest(
        benchmark_id="typed-benchmark",
        dataset_name="unit-fixtures",
        dataset_version="1",
        cases=tuple(cases or _cases()),
        protocol_id="typed-v1",
        metric_definitions=(_definition(),),
    )


def _context(seed: int = 99) -> BenchmarkRunContext:
    return BenchmarkRunContext(
        code_commit="a" * 40,
        environment_fingerprint_sha256="b" * 64,
        command=("python", "benchmark.py"),
        seed=seed,
    )


def test_case_seed_is_stable_when_manifest_order_changes() -> None:
    cases = _cases()
    forward = {case.case_id: benchmark_case_seed(17, case) for case in cases}
    reverse = {case.case_id: benchmark_case_seed(17, case) for case in reversed(cases)}
    assert forward == reverse
    assert len(set(forward.values())) == len(cases)


def test_metric_schema_aggregation_confidence_and_failure_inclusive_pass_rate(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    artifact = root / "case-0.json"
    artifact.write_text('{"pose": 0}', encoding="utf-8")
    artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()

    def evaluator(case, seed):
        assert seed == benchmark_case_seed(99, case)
        if case.case_id == "case-1":
            raise RuntimeError("/private/customer/target.pdb token=secret")
        value = 1.0 if case.case_id == "case-0" else 3.0
        return BenchmarkCaseResult(
            metrics={"pose_rmsd_angstrom": value},
            artifact_sha256=artifact_sha if case.case_id == "case-0" else "",
            artifact_path="case-0.json" if case.case_id == "case-0" else "",
            artifact_media_type="application/json" if case.case_id == "case-0" else "",
        )

    report = run_benchmark_manifest(
        _manifest(),
        _context(),
        evaluator,
        artifact_root=root,
    )
    assert report.complete
    assert report.success_count == 2
    assert report.failure_count == 1
    summary = report.metric_summaries[0]
    assert summary.aggregate_value == pytest.approx(2.0)
    assert summary.observed_count == 2
    assert summary.total_case_count == 3
    assert summary.coverage_rate == pytest.approx(2.0 / 3.0)
    assert summary.pass_count == 1
    assert summary.pass_rate_all_cases == pytest.approx(1.0 / 3.0)
    assert summary.confidence_interval_low is not None
    assert summary.confidence_interval_high is not None
    assert report.rows[0].artifact_verified is True
    assert report.rows[0].artifact_size_bytes == len(artifact.read_bytes())
    assert report.rows[1].error_message == "benchmark case evaluation failed"
    assert "private" not in report.rows[1].error_message
    assert len(report.rows[1].private_error_sha256) == 64


def test_metric_schema_rejects_missing_undeclared_and_out_of_range_values() -> None:
    for metrics in (
        {},
        {"other": 1.0},
        {"pose_rmsd_angstrom": -1.0},
    ):
        def evaluator(case, seed, metrics=metrics):
            del case, seed
            return BenchmarkCaseResult(metrics=metrics)

        report = run_benchmark_manifest(_manifest(), _context(), evaluator)
        assert report.success_count == 0
        assert report.failure_count == 3
        assert all(row.error_code == "BenchmarkContractError" for row in report.rows)
        assert all(row.error_message == "benchmark case evaluation failed" for row in report.rows)


def test_actual_artifact_hash_path_and_symlink_are_verified_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    artifact = root / "pose.sdf"
    artifact.write_text("pose", encoding="utf-8")

    def mismatch(case, seed):
        del case, seed
        return BenchmarkCaseResult(
            metrics={"pose_rmsd_angstrom": 1.0},
            artifact_sha256="f" * 64,
            artifact_path="pose.sdf",
        )

    report = run_benchmark_manifest(_manifest(), _context(), mismatch, artifact_root=root)
    assert report.failure_count == 3
    assert all(row.error_code == "BenchmarkContractError" for row in report.rows)

    outside = tmp_path / "outside.sdf"
    outside.write_text("secret", encoding="utf-8")
    symlink = root / "link.sdf"
    try:
        symlink.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")

    def linked(case, seed):
        del case, seed
        return BenchmarkCaseResult(
            metrics={"pose_rmsd_angstrom": 1.0},
            artifact_path="link.sdf",
        )

    linked_report = run_benchmark_manifest(_manifest(), _context(), linked, artifact_root=root)
    assert linked_report.failure_count == 3
    assert all(row.error_code == "BenchmarkContractError" for row in linked_report.rows)


def test_atomic_signed_report_verifies_and_detects_tampering(tmp_path: Path) -> None:
    def evaluator(case, seed):
        del case, seed
        return BenchmarkCaseResult(metrics={"pose_rmsd_angstrom": 1.5})

    report = run_benchmark_manifest(_manifest(), _context(), evaluator)
    path = report.write_json(
        tmp_path / "signed-report.json",
        signing_key="unit-secret",
        key_id="unit-key",
    )
    assert path.exists()
    assert not list(tmp_path.glob(".signed-report.json.tmp-*"))
    verified = verify_signed_benchmark_report(
        path.read_bytes(),
        keys={"unit-key": "unit-secret"},
    )
    assert verified["signature"]["key_id"] == "unit-key"
    assert verified["failure_count"] == 0

    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["rows"][0]["metrics"]["pose_rmsd_angstrom"] = 9.0
    with pytest.raises(BenchmarkContractError, match="HMAC verification failed"):
        verify_signed_benchmark_report(tampered, keys={"unit-key": "unit-secret"})


def test_report_constructor_detects_order_or_seed_drift() -> None:
    def evaluator(case, seed):
        del case, seed
        return BenchmarkCaseResult(metrics={"pose_rmsd_angstrom": 1.0})

    report = run_benchmark_manifest(_manifest(), _context(), evaluator)
    with pytest.raises(BenchmarkContractError, match="stable case seed"):
        type(report)(
            manifest=report.manifest,
            context=report.context,
            rows=(
                type(report.rows[0])(
                    **{
                        **report.rows[0].__dict__,
                        "seed": report.rows[0].seed + 1,
                    }
                ),
                *report.rows[1:],
            ),
        )
