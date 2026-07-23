from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import zipfile

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_external_ranking_evaluation as evaluation_module,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_external_ranking_reproduction as reproduction_module,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_external_ranking_evaluation import (  # noqa: E402
    materialize_posebusters_external_ranking_evaluation,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_external_ranking_reproduction import (  # noqa: E402
    POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_SCIENTIFIC_BLOCKERS,
    PoseBustersExternalRankingReproductionError,
    materialize_posebusters_external_ranking_reproduction_result,
    materialize_posebusters_external_ranking_reproduction_work_order,
    verify_posebusters_external_ranking_reproduction_result,
    verify_posebusters_external_ranking_reproduction_work_order,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_pose_ranking_intake import (  # noqa: E402
    POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
)
from tests.unit.test_engine_v2_posebusters_external_ranking_evaluation import (  # noqa: E402
    _fixture as _evaluation_partition_fixture,
)
from tests.unit.test_engine_v2_posebusters_external_ranking_evaluation import (  # noqa: E402
    _sha,
    _write_receipt,
)


_FIXED_ROLES = (
    "archive_intake",
    "external_preparation",
    "rcsb_pfam_target_family",
)
_ENGINE_ROLES = (
    "vina_execution",
    "vina_evaluation",
    "gnina_execution",
    "gnina_evaluation",
    "smina_execution",
    "smina_evaluation",
)
_BASELINE_HOST = _sha("baseline-host")
_EXTERNAL_HOST = _sha("external-host")
_WORK_ORDER_OPERATOR = _sha("work-order-operator")
_EXTERNAL_EXECUTOR = _sha("external-executor")
_EXECUTION_NONCE = _sha("single-use-execution-nonce")


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _intake_payload(tag: str, *, fixed_tag: str = "fixed") -> dict[str, object]:
    input_receipts = []
    for role in _FIXED_ROLES:
        input_receipts.append(
            {
                "role": role,
                "source_schema_id": f"fixture.{role}/1.0.0",
                "source_receipt_sha256": _sha(f"{fixed_tag}:{role}:receipt"),
                "source_file_sha256": _sha(f"{fixed_tag}:{role}:file"),
            }
        )
    for role in _ENGINE_ROLES:
        input_receipts.append(
            {
                "role": role,
                "source_schema_id": f"fixture.{role}/1.0.0",
                "source_receipt_sha256": _sha(f"{tag}:{role}:receipt"),
                "source_file_sha256": _sha(f"{tag}:{role}:file"),
            }
        )
    return {
        "schema_id": POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
        "dataset_id": "posebusters-test",
        "dataset_version": "fixture-v1",
        "configuration_sha256": _sha("ranking-intake-configuration"),
        "implementation_source_sha256": _sha("ranking-intake-implementation"),
        "all_case_denominator": 308,
        "split_role": "test",
        "input_receipts": input_receipts,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _mutate_vina_score(
    partition_payload: dict[str, object],
    *,
    offset: float,
) -> None:
    engine_partitions = partition_payload["engine_partitions"]
    assert isinstance(engine_partitions, list)
    vina = next(
        row
        for row in engine_partitions
        if isinstance(row, dict) and row["engine_id"] == "vina"
    )
    partition_document = vina["partition"]
    assert isinstance(partition_document, dict)
    rows = partition_document["rows"]
    assert isinstance(rows, list)
    success = next(
        row for row in rows if isinstance(row, dict) and row["status"] == "success"
    )
    terms = success["term_values"]
    assert isinstance(terms, dict)
    terms["vina.total"] = float(terms["vina.total"]) + offset
    partition = evaluation_module._calibration_partition(partition_document)
    vina["partition_fingerprint_sha256"] = partition.fingerprint_sha256
    vina["partition_identity_fingerprint_sha256"] = (
        partition.identity_fingerprint_sha256
    )


def _write_chain(
    root: Path,
    partition_template: dict[str, object],
    *,
    tag: str,
    fixed_tag: str = "fixed",
    vina_score_offset: float = 0.0,
) -> dict[str, object]:
    root.mkdir(parents=True)
    intake_path = root / "ranking-intake.json"
    intake_sha = _write_receipt(
        intake_path,
        _intake_payload(tag, fixed_tag=fixed_tag),
    )
    partition_payload = deepcopy(partition_template)
    partition_payload["input_receipts"] = [
        {
            "role": "pose_ranking_intake",
            "source_schema_id": POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
            "source_receipt_sha256": intake_sha,
            "source_file_sha256": _file_sha(intake_path),
        }
    ]
    if vina_score_offset:
        _mutate_vina_score(
            partition_payload,
            offset=vina_score_offset,
        )
    partition_path = root / "test-partitions.json"
    partition_sha = _write_receipt(partition_path, partition_payload)
    evaluation = materialize_posebusters_external_ranking_evaluation(
        partition_path,
        expected_test_partition_receipt_sha256=partition_sha,
    )
    evaluation_path = root / "ranking-evaluation.json"
    evaluation.write_json(evaluation_path)
    return {
        "ranking_intake_receipt_path": intake_path,
        "expected_ranking_intake_receipt_sha256": intake_sha,
        "test_partition_receipt_path": partition_path,
        "expected_test_partition_receipt_sha256": partition_sha,
        "evaluation_receipt_path": evaluation_path,
        "expected_evaluation_receipt_sha256": (evaluation.fingerprint_sha256),
    }


def _wheel(root: Path) -> tuple[Path, str]:
    path = root / "betelgeuze_engine_v2-0.2.0rc2-py3-none-any.whl"
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for _role, _digest, member_path in reproduction_module._source_members():
            archive.writestr(member_path, Path(member_path).read_bytes())
    return path, _file_sha(path)


@pytest.fixture(scope="module")
def chains(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("external-ranking-reproduction")
    seed_path, _seed_sha = _evaluation_partition_fixture(root / "seed")
    template = json.loads(seed_path.read_text(encoding="ascii"))
    template.pop("receipt_sha256")
    baseline = _write_chain(root / "baseline", template, tag="baseline")
    external = _write_chain(root / "external", template, tag="external")
    score_mismatch = _write_chain(
        root / "score-mismatch",
        template,
        tag="score-mismatch",
        vina_score_offset=0.001,
    )
    changed_input = _write_chain(
        root / "changed-input",
        template,
        tag="changed-input",
        fixed_tag="changed-fixed",
    )
    wheel_path, wheel_sha = _wheel(root)
    return {
        "root": root,
        "baseline": baseline,
        "external": external,
        "score_mismatch": score_mismatch,
        "changed_input": changed_input,
        "wheel_path": wheel_path,
        "wheel_sha": wheel_sha,
    }


def _baseline_arguments(chains: dict[str, object]) -> dict[str, object]:
    baseline = chains["baseline"]
    assert isinstance(baseline, dict)
    return {
        "baseline_evaluation_receipt_path": baseline["evaluation_receipt_path"],
        "baseline_test_partition_receipt_path": baseline["test_partition_receipt_path"],
        "baseline_ranking_intake_receipt_path": baseline["ranking_intake_receipt_path"],
        "engine_wheel_path": chains["wheel_path"],
        "expected_baseline_evaluation_receipt_sha256": baseline[
            "expected_evaluation_receipt_sha256"
        ],
        "expected_baseline_test_partition_receipt_sha256": baseline[
            "expected_test_partition_receipt_sha256"
        ],
        "expected_baseline_ranking_intake_receipt_sha256": baseline[
            "expected_ranking_intake_receipt_sha256"
        ],
        "expected_engine_wheel_sha256": chains["wheel_sha"],
    }


def _external_arguments(chain: dict[str, object]) -> dict[str, object]:
    return {
        "external_evaluation_receipt_path": chain["evaluation_receipt_path"],
        "external_test_partition_receipt_path": chain["test_partition_receipt_path"],
        "external_ranking_intake_receipt_path": chain["ranking_intake_receipt_path"],
        "expected_external_evaluation_receipt_sha256": chain[
            "expected_evaluation_receipt_sha256"
        ],
        "expected_external_test_partition_receipt_sha256": chain[
            "expected_test_partition_receipt_sha256"
        ],
        "expected_external_ranking_intake_receipt_sha256": chain[
            "expected_ranking_intake_receipt_sha256"
        ],
    }


def _work_order(
    chains: dict[str, object],
    output: Path,
) -> tuple[object, dict[str, object]]:
    baseline = _baseline_arguments(chains)
    receipt = materialize_posebusters_external_ranking_reproduction_work_order(
        **baseline,
        baseline_host_identity_sha256=_BASELINE_HOST,
        expected_external_host_identity_sha256=_EXTERNAL_HOST,
        work_order_operator_identity_sha256=_WORK_ORDER_OPERATOR,
        external_execution_operator_identity_sha256=_EXTERNAL_EXECUTOR,
        external_execution_nonce_sha256=_EXECUTION_NONCE,
        registered_utc="2026-07-24T00:00:00Z",
    )
    receipt.write_json(output)
    return receipt, baseline


def test_preregisters_role_separated_work_order_and_exactly_verifies(
    tmp_path: Path,
    chains: dict[str, object],
) -> None:
    output = tmp_path / "work-order.json"
    receipt, baseline = _work_order(chains, output)
    payload = receipt.to_dict()

    assert payload["all_case_denominator"] == 308
    assert payload["engine_count"] == 3
    assert payload["external_execution_performed"] is False
    assert payload["cross_host_comparison_present"] is False
    assert payload["independent_external_rerun_present"] is False
    assert payload["claim_safe"] is False
    assert len(payload["fixed_input_receipts"]) == 3
    assert len(payload["baseline_engine_evidence_receipts"]) == 6
    assert output.stat().st_mode & 0o777 == 0o600

    verified = verify_posebusters_external_ranking_reproduction_work_order(
        work_order_path=output,
        expected_work_order_receipt_sha256=receipt.fingerprint_sha256,
        **baseline,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    with pytest.raises(
        PoseBustersExternalRankingReproductionError,
        match="already exists",
    ):
        receipt.write_json(output)

    with pytest.raises(
        PoseBustersExternalRankingReproductionError,
        match="role-separated",
    ):
        materialize_posebusters_external_ranking_reproduction_work_order(
            **baseline,
            baseline_host_identity_sha256=_BASELINE_HOST,
            expected_external_host_identity_sha256=_BASELINE_HOST,
            work_order_operator_identity_sha256=_WORK_ORDER_OPERATOR,
            external_execution_operator_identity_sha256=_EXTERNAL_EXECUTOR,
            external_execution_nonce_sha256=_EXECUTION_NONCE,
            registered_utc="2026-07-24T00:00:00Z",
        )
    with pytest.raises(
        PoseBustersExternalRankingReproductionError,
        match="must not reuse an identity",
    ):
        materialize_posebusters_external_ranking_reproduction_work_order(
            **baseline,
            baseline_host_identity_sha256=_BASELINE_HOST,
            expected_external_host_identity_sha256=_EXTERNAL_HOST,
            work_order_operator_identity_sha256=_WORK_ORDER_OPERATOR,
            external_execution_operator_identity_sha256=_EXTERNAL_EXECUTOR,
            external_execution_nonce_sha256=_BASELINE_HOST,
            registered_utc="2026-07-24T00:00:00Z",
        )


def test_compares_all_cases_and_keeps_independence_claim_closed(
    tmp_path: Path,
    chains: dict[str, object],
) -> None:
    work_order_path = tmp_path / "work-order.json"
    work_order, baseline = _work_order(chains, work_order_path)
    external = chains["external"]
    assert isinstance(external, dict)
    result = materialize_posebusters_external_ranking_reproduction_result(
        work_order_path=work_order_path,
        expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
        **baseline,
        **_external_arguments(external),
        observed_external_host_identity_sha256=_EXTERNAL_HOST,
        observed_external_execution_operator_identity_sha256=(_EXTERNAL_EXECUTOR),
        external_observed_utc="2026-07-24T01:00:00Z",
    )
    payload = result.to_dict()

    assert payload["status"] == "comparison_passed"
    assert payload["cross_host_numerical_reproduction_pass"] is True
    assert payload["comparison"]["case_comparison_count"] == 924
    assert payload["comparison"]["reproduced_case_count"] == 924
    assert payload["all_failure_rows_compared"] is True
    assert payload["physical_host_independence_reviewed"] is False
    assert payload["independent_external_rerun_present"] is False
    assert payload["scientific_blockers"] == list(
        POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_SCIENTIFIC_BLOCKERS
    )
    assert payload["claim_safe"] is False
    for engine in payload["comparison"]["engine_rows"]:
        assert engine["case_comparison_count"] == 308
        assert engine["reproduced_case_count"] == 308
        assert engine["family_scope_comparison"]["family_scopes_reproduced"] is True

    output = tmp_path / "result.json"
    result.write_json(output)
    verified = verify_posebusters_external_ranking_reproduction_result(
        result_path=output,
        expected_result_receipt_sha256=result.fingerprint_sha256,
        work_order_path=work_order_path,
        expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
        **baseline,
        **_external_arguments(external),
    )
    assert verified.fingerprint_sha256 == result.fingerprint_sha256


def test_rejects_replay_and_fixed_input_change_and_flags_score_drift(
    tmp_path: Path,
    chains: dict[str, object],
) -> None:
    work_order_path = tmp_path / "work-order.json"
    work_order, baseline = _work_order(chains, work_order_path)
    baseline_chain = chains["baseline"]
    changed_input = chains["changed_input"]
    score_mismatch = chains["score_mismatch"]
    assert isinstance(baseline_chain, dict)
    assert isinstance(changed_input, dict)
    assert isinstance(score_mismatch, dict)
    common = {
        "work_order_path": work_order_path,
        "expected_work_order_receipt_sha256": (work_order.fingerprint_sha256),
        **baseline,
        "observed_external_host_identity_sha256": _EXTERNAL_HOST,
        "observed_external_execution_operator_identity_sha256": (_EXTERNAL_EXECUTOR),
        "external_observed_utc": "2026-07-24T01:00:00Z",
    }

    with pytest.raises(
        PoseBustersExternalRankingReproductionError,
        match="reuses a baseline result receipt",
    ):
        materialize_posebusters_external_ranking_reproduction_result(
            **common,
            **_external_arguments(baseline_chain),
        )
    with pytest.raises(
        PoseBustersExternalRankingReproductionError,
        match="changed a fixed same-input public root",
    ):
        materialize_posebusters_external_ranking_reproduction_result(
            **common,
            **_external_arguments(changed_input),
        )

    result = materialize_posebusters_external_ranking_reproduction_result(
        **common,
        **_external_arguments(score_mismatch),
    ).to_dict()
    assert result["status"] == "comparison_failed"
    assert result["cross_host_numerical_reproduction_pass"] is False
    assert result["comparison"]["reproduced_case_count"] == 923
    vina = result["comparison"]["engine_rows"][0]
    failed = [row for row in vina["case_rows"] if not row["case_reproduced"]]
    assert len(failed) == 1
    assert failed[0]["source_score_tolerance_pass"] is False


@pytest.mark.parametrize(
    ("host_identity", "executor_identity", "observed_utc", "message"),
    (
        (
            _sha("unregistered-external-host"),
            _EXTERNAL_EXECUTOR,
            "2026-07-24T01:00:00Z",
            "external host or execution operator was not preregistered",
        ),
        (
            _EXTERNAL_HOST,
            _sha("unregistered-external-executor"),
            "2026-07-24T01:00:00Z",
            "external host or execution operator was not preregistered",
        ),
        (
            _EXTERNAL_HOST,
            _EXTERNAL_EXECUTOR,
            "2026-07-24T00:00:00Z",
            "external observation must follow work-order registration",
        ),
    ),
)
def test_rejects_unregistered_execution_identity_and_pre_registration_observation(
    tmp_path: Path,
    chains: dict[str, object],
    host_identity: str,
    executor_identity: str,
    observed_utc: str,
    message: str,
) -> None:
    work_order_path = tmp_path / "work-order.json"
    work_order, baseline = _work_order(chains, work_order_path)
    external = chains["external"]
    assert isinstance(external, dict)

    with pytest.raises(PoseBustersExternalRankingReproductionError, match=message):
        materialize_posebusters_external_ranking_reproduction_result(
            work_order_path=work_order_path,
            expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
            **baseline,
            **_external_arguments(external),
            observed_external_host_identity_sha256=host_identity,
            observed_external_execution_operator_identity_sha256=executor_identity,
            external_observed_utc=observed_utc,
        )
