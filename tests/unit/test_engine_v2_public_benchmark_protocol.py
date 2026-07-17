from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil

import pytest

from betelgeuze_engine_v2.benchmark import (
    BOUNDED_VALIDITY_METRIC_ID,
    FROZEN_PUBLIC_BENCHMARK_PROTOCOL_SHA256,
    POSEBUSTERS_SOURCE_COMMIT_SHA,
    PRIMARY_RMSD_METRIC_ID,
    PRIMARY_SUCCESS_METRIC_ID,
    PUBLIC_BENCHMARK_PROTOCOL_SCHEMA_ID,
    BenchmarkCaseResult,
    BenchmarkRunContext,
    PublicBenchmarkArtifact,
    PublicBenchmarkProtocolError,
    frozen_public_benchmark_protocol,
    public_benchmark_protocol_document,
    public_benchmark_protocol_json_bytes,
    require_public_benchmark_case_metrics,
    require_public_benchmark_protocol_document,
    require_public_benchmark_report,
    run_benchmark_manifest,
    verify_public_benchmark_scorer_sources,
    write_public_benchmark_protocol_json,
)


def test_frozen_protocol_binds_exact_source_cases_metrics_and_digest() -> None:
    protocol = frozen_public_benchmark_protocol()

    assert protocol.schema_id == PUBLIC_BENCHMARK_PROTOCOL_SCHEMA_ID
    assert protocol.protocol_sha256 == FROZEN_PUBLIC_BENCHMARK_PROTOCOL_SHA256
    assert protocol.protocol_sha256 == (
        "4ae0919cdbb65038cb64bd5fb014c99cd6107de9d25852c67c313cf3459e089c"
    )
    assert POSEBUSTERS_SOURCE_COMMIT_SHA == ("1a5f26aa7270fafba21b7fec8b3633f4c4e45ead")
    assert [case.pdb_id for case in protocol.cases] == [
        "1ia1",
        "1of6",
        "1s3v",
        "1uou",
    ]
    assert [case.input_sha256 for case in protocol.cases] == [
        "531733edccb0fe2256a1f7606e171d0ab38bf07b641abeb4bf30d165fc647e94",
        "3ad6655806497a9d1c7523a4ab4445aa745f3add23b47bf5c681fd8cabe3da3c",
        "5b2509f56f09a8cfc98396ad10a9c52aa2802a5f192c197b3ddcae5b5e67fd96",
        "6bf9efd833af14518faa9cb674e2623c7e97ed416dbf71cea6f867e81b55c0f1",
    ]
    manifest = protocol.benchmark_manifest
    assert manifest.fingerprint_sha256 == (
        "9df57fdf0b694af42e668180a890a9c5686e1284aed334f3b3334343ca14eba8"
    )
    assert [definition.metric_id for definition in manifest.metric_definitions] == [
        PRIMARY_RMSD_METRIC_ID,
        BOUNDED_VALIDITY_METRIC_ID,
        PRIMARY_SUCCESS_METRIC_ID,
    ]
    assert manifest.metric_definition_map[PRIMARY_RMSD_METRIC_ID].pass_threshold == 2.0
    assert manifest.metadata["failure_rows_retained"] is True
    assert manifest.metadata["denominator"] == "all_manifest_cases"


def test_protocol_keeps_source_licensing_and_nonpromotion_boundaries_explicit() -> None:
    document = public_benchmark_protocol_document()
    source = document["source"]

    assert source["repository_license"]["spdx_id"] == "MIT"
    assert source["underlying_structure_archive_license"]["spdx_id"] == "CC0-1.0"
    assert source["license_metadata_reviewed"] is True
    assert source["legal_compliance_approved"] is False
    execution = document["execution_policy"]
    for key in (
        "network_fetch_implemented",
        "raw_data_bundled",
        "benchmark_execution_authorized",
        "result_document_created",
        "result_publication_authorized",
        "test_set_tuning_allowed",
        "ligand_identity_seed_coordinates_used",
    ):
        assert execution[key] is False
    assert "environment_fingerprint_sha256" in execution["future_report_must_bind"]
    assert document["split_policy"]["scientific_holdout_status"] == "not_established"
    assert document["review"]["revoked"] is False
    assert document["review"]["superseded"] is False
    claims = document["claim_policy"]
    assert claims["protocol_definition_frozen"] is True
    assert claims["license_metadata_reviewed"] is True
    for key in (
        "legal_compliance_approved",
        "statistical_representativeness_established",
        "scientifically_validated",
        "public_benchmark_validation",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert claims[key] is False
    assert "public_benchmark_not_executed" in document["blockers"]
    assert "posebusters_benchmark_equivalence_not_established" in document["blockers"]


def test_raw_inputs_are_external_commit_bound_and_not_bundled() -> None:
    protocol = frozen_public_benchmark_protocol()
    for case in protocol.cases:
        for artifact in (
            case.receptor,
            case.reference_ligands,
            case.ligand_identity_seed,
        ):
            payload = artifact.to_dict()
            assert payload["bundled"] is False
            assert artifact.immutable_url.startswith(
                "https://raw.githubusercontent.com/"
            )
            assert POSEBUSTERS_SOURCE_COMMIT_SHA in artifact.immutable_url
            assert artifact.relative_path in artifact.immutable_url
            assert len(artifact.sha256) == 64
            assert artifact.size_bytes > 0
    endpoint = protocol.to_dict()["endpoint_policy"]
    assert endpoint["receptor_frame_required"] is True
    assert endpoint["ligand_only_alignment_allowed"] is False
    assert endpoint["ligand_identity_seed_coordinates_used"] is False
    assert "direct_receptor_frame_rmsd" in endpoint["rmsd_method"]


def test_artifact_byte_verifier_is_offline_and_fail_closed() -> None:
    raw = b"frozen public fixture\n"
    artifact = PublicBenchmarkArtifact(
        role="receptor",
        relative_path="fixture.pdb",
        immutable_url=(
            f"https://example.invalid/{POSEBUSTERS_SOURCE_COMMIT_SHA}/fixture.pdb"
        ),
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        media_type="chemical/x-pdb",
    )
    assert artifact.verify_bytes(raw) == artifact.sha256
    with pytest.raises(PublicBenchmarkProtocolError, match="size mismatch"):
        artifact.verify_bytes(raw + b"x")
    with pytest.raises(PublicBenchmarkProtocolError, match="SHA-256 mismatch"):
        artifact.verify_bytes(b"x" * len(raw))

    with pytest.raises(PublicBenchmarkProtocolError, match="source repository"):
        replace(artifact, relative_path="../fixture.pdb")


@pytest.mark.parametrize(
    ("rmsd", "validity", "primary"),
    (
        (1.999, 1.0, 1.0),
        (2.0, 1.0, 1.0),
        (2.001, 1.0, 0.0),
        (1.0, 0.0, 0.0),
    ),
)
def test_primary_endpoint_rule_is_frozen(
    rmsd: float,
    validity: float,
    primary: float,
) -> None:
    metrics = {
        PRIMARY_RMSD_METRIC_ID: rmsd,
        BOUNDED_VALIDITY_METRIC_ID: validity,
        PRIMARY_SUCCESS_METRIC_ID: primary,
    }
    assert require_public_benchmark_case_metrics(metrics) is metrics


def test_primary_endpoint_rejects_schema_or_conjunction_drift() -> None:
    with pytest.raises(PublicBenchmarkProtocolError, match="endpoint schema"):
        require_public_benchmark_case_metrics({PRIMARY_RMSD_METRIC_ID: 1.0})
    with pytest.raises(PublicBenchmarkProtocolError, match="exactly 0 or 1"):
        require_public_benchmark_case_metrics(
            {
                PRIMARY_RMSD_METRIC_ID: 1.0,
                BOUNDED_VALIDITY_METRIC_ID: 0.5,
                PRIMARY_SUCCESS_METRIC_ID: 0.0,
            }
        )
    with pytest.raises(PublicBenchmarkProtocolError, match="disagrees"):
        require_public_benchmark_case_metrics(
            {
                PRIMARY_RMSD_METRIC_ID: 1.0,
                BOUNDED_VALIDITY_METRIC_ID: 1.0,
                PRIMARY_SUCCESS_METRIC_ID: 0.0,
            }
        )
    with pytest.raises(PublicBenchmarkProtocolError, match=r"finite and in \[0,100\]"):
        require_public_benchmark_case_metrics(
            {
                PRIMARY_RMSD_METRIC_ID: float("nan"),
                BOUNDED_VALIDITY_METRIC_ID: 1.0,
                PRIMARY_SUCCESS_METRIC_ID: 0.0,
            }
        )


def test_failure_inclusive_report_contract_keeps_all_four_rows() -> None:
    protocol = frozen_public_benchmark_protocol()

    def evaluator(case, seed):
        del seed
        if case.case_id.endswith("1of6"):
            raise RuntimeError("synthetic contract failure only")
        return BenchmarkCaseResult(
            metrics={
                PRIMARY_RMSD_METRIC_ID: 1.5,
                BOUNDED_VALIDITY_METRIC_ID: 1.0,
                PRIMARY_SUCCESS_METRIC_ID: 1.0,
            }
        )

    report = run_benchmark_manifest(
        protocol.benchmark_manifest,
        BenchmarkRunContext(
            code_commit="a" * 40,
            environment_fingerprint_sha256="b" * 64,
            command=("synthetic-unit-contract",),
            seed=17,
        ),
        evaluator,
    )
    assert require_public_benchmark_report(report) is report
    assert len(report.rows) == 4
    assert report.success_count == 3
    assert report.failure_count == 1
    assert report.metric_summaries[2].pass_rate_all_cases == pytest.approx(0.75)
    assert report.claim_safe is False


def test_report_contract_rejects_manifest_or_primary_metric_drift() -> None:
    protocol = frozen_public_benchmark_protocol()

    def evaluator(case, seed):
        del case, seed
        return BenchmarkCaseResult(
            metrics={
                PRIMARY_RMSD_METRIC_ID: 1.0,
                BOUNDED_VALIDITY_METRIC_ID: 1.0,
                PRIMARY_SUCCESS_METRIC_ID: 0.0,
            }
        )

    report = run_benchmark_manifest(
        protocol.benchmark_manifest,
        BenchmarkRunContext(
            code_commit="c" * 40,
            environment_fingerprint_sha256="d" * 64,
            command=("synthetic-unit-contract",),
            seed=18,
        ),
        evaluator,
    )
    with pytest.raises(PublicBenchmarkProtocolError, match="disagrees"):
        require_public_benchmark_report(report)

    other_manifest = replace(protocol.benchmark_manifest, protocol_id="drifted")
    with pytest.raises(PublicBenchmarkProtocolError, match="manifest"):
        require_public_benchmark_report(replace(report, manifest=other_manifest))


def test_document_round_trip_tamper_detection_and_private_atomic_writer(
    tmp_path: Path,
) -> None:
    raw = public_benchmark_protocol_json_bytes()
    loaded = json.loads(raw)
    assert require_public_benchmark_protocol_document(loaded) == loaded
    assert raw == (
        json.dumps(
            loaded,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )

    tampered = json.loads(raw)
    tampered["execution_policy"]["benchmark_execution_authorized"] = True
    with pytest.raises(PublicBenchmarkProtocolError, match="drifted"):
        require_public_benchmark_protocol_document(tampered)

    path = write_public_benchmark_protocol_json(tmp_path / "protocol.json")
    assert path.read_bytes() == raw
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".protocol.json.*.tmp"))


def test_scorer_source_identities_verify_and_detect_checkout_drift(
    tmp_path: Path,
) -> None:
    observed = verify_public_benchmark_scorer_sources(Path.cwd())
    assert set(observed) == {
        "failure_inclusive_report",
        "pose_validity",
        "symmetry_aware_rmsd",
    }

    protocol = frozen_public_benchmark_protocol()
    for identity in protocol.scorer_identities:
        target = tmp_path / identity.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(identity.relative_path, target)
    assert verify_public_benchmark_scorer_sources(tmp_path) == observed

    drifted = tmp_path / protocol.scorer_identities[0].relative_path
    drifted.write_bytes(drifted.read_bytes() + b"\n# drift\n")
    with pytest.raises(PublicBenchmarkProtocolError, match="SHA-256 mismatch"):
        verify_public_benchmark_scorer_sources(tmp_path)


def test_protocol_module_contains_no_network_or_process_execution_surface() -> None:
    source = Path("betelgeuze_engine_v2/benchmark/public_protocol.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "urllib.request",
        "requests.",
        "httpx.",
        "subprocess",
        "urlopen(",
        "socket.",
    ):
        assert forbidden not in source


def test_dedicated_protocol_workflow_is_hosted_and_has_no_fetch_step() -> None:
    source = Path(
        ".github/workflows/ci-engine-v2-public-benchmark-protocol.yml"
    ).read_text(encoding="utf-8")
    assert "runs-on: ubuntu-latest" in source
    assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    assert "self-hosted" not in source
    assert "persist-credentials: false" in source
    assert "test_engine_v2_public_benchmark_protocol.py" in source
    assert "curl " not in source
    assert "wget " not in source
