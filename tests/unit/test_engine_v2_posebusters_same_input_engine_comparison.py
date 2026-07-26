from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_external_generated_pose_evaluation as external_module,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_generated_pose_evaluation as vina_module,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_internal_oracle_evaluation as oracle_module,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_same_input_engine_comparison as comparison,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_same_input_engine_comparison import (  # noqa: E402
    POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_BLOCKERS,
    PoseBustersSameInputEngineComparisonError,
    materialize_posebusters_same_input_engine_comparison,
    verify_posebusters_same_input_engine_comparison_receipt,
)


_CASE_IDS = ("1ABC_AAA", "2DEF_BBB", "3GHI_CCC")
_INTAKE = hashlib.sha256(b"shared-archive-intake").hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _write_receipt(path: Path, payload: dict[str, object]) -> str:
    receipt_sha = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    document = {**payload, "receipt_sha256": receipt_sha}
    path.write_bytes(_canonical_bytes(document) + b"\n")
    path.chmod(0o600)
    return receipt_sha


def _pose(
    *,
    rank: int,
    status: str = "evaluated",
    valid: bool = True,
    rmsd_evaluated: bool = True,
    rmsd_hit: bool = True,
) -> dict[str, object]:
    return {
        "pose_rank": rank,
        "status": status,
        "all_non_rmsd_binary_tests_pass": valid,
        "rmsd_evaluated": rmsd_evaluated,
        "rmsd_within_2_angstrom": rmsd_hit,
    }


def _case(
    case_id: str,
    *,
    status: str = "evaluated",
    poses: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    return {"case_id": case_id, "status": status, "pose_results": list(poses)}


def _engine_payload(
    *,
    schema_id: str,
    cases: tuple[dict[str, object], ...],
    intake: str = _INTAKE,
    engine_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": schema_id,
        "archive_intake_receipt_sha256": intake,
        "all_case_denominator": len(cases),
        "case_rows": list(cases),
        "benchmark_executed": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    if engine_id is not None:
        payload["engine_id"] = engine_id
    return payload


def _fixture(
    tmp_path: Path,
    *,
    intake_overrides: dict[str, str] | None = None,
) -> dict[str, object]:
    overrides = intake_overrides or {}
    internal_cases = (
        _case(_CASE_IDS[0], poses=(_pose(rank=1), _pose(rank=2))),
        _case(
            _CASE_IDS[1],
            status="evaluation_failure",
            poses=(
                _pose(
                    rank=1,
                    status="evaluation_failure",
                    valid=False,
                    rmsd_evaluated=False,
                    rmsd_hit=False,
                ),
            ),
        ),
        _case(_CASE_IDS[2], status="blocked_upstream"),
    )
    vina_cases = (
        _case(_CASE_IDS[0], poses=(_pose(rank=1),)),
        _case(_CASE_IDS[1], poses=(_pose(rank=1, rmsd_hit=False),)),
        _case(_CASE_IDS[2], status="blocked_engine_failure"),
    )
    gnina_cases = (
        _case(_CASE_IDS[0], poses=(_pose(rank=1, valid=False),)),
        _case(_CASE_IDS[1], status="abstain_chemistry_scope"),
    )
    smina_cases = (
        _case(_CASE_IDS[0], poses=(_pose(rank=1),)),
        _case(_CASE_IDS[1], poses=(_pose(rank=1, rmsd_hit=False),)),
        _case(_CASE_IDS[2], poses=(_pose(rank=1, rmsd_hit=False),)),
    )
    external_schema = (
        external_module.POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID
    )
    rows = {
        "internal": (
            oracle_module.POSEBUSTERS_INTERNAL_ORACLE_EVALUATION_SCHEMA_ID,
            internal_cases,
            None,
        ),
        "vina": (
            vina_module.POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID,
            vina_cases,
            None,
        ),
        "gnina": (external_schema, gnina_cases, "gnina"),
        "smina": (external_schema, smina_cases, "smina"),
    }
    fixture: dict[str, object] = {}
    for engine_id, (schema_id, cases, payload_engine) in rows.items():
        path = tmp_path / f"{engine_id}.json"
        digest = _write_receipt(
            path,
            _engine_payload(
                schema_id=schema_id,
                cases=cases,
                intake=overrides.get(engine_id, _INTAKE),
                engine_id=payload_engine,
            ),
        )
        fixture[f"{engine_id}_path"] = path
        fixture[f"{engine_id}_sha256"] = digest
    return fixture


def _arguments(fixture: dict[str, object]) -> dict[str, object]:
    return {
        "internal_oracle_receipt_path": fixture["internal_path"],
        "vina_evaluation_receipt_path": fixture["vina_path"],
        "gnina_evaluation_receipt_path": fixture["gnina_path"],
        "smina_evaluation_receipt_path": fixture["smina_path"],
        "expected_internal_oracle_receipt_sha256": fixture["internal_sha256"],
        "expected_vina_evaluation_receipt_sha256": fixture["vina_sha256"],
        "expected_gnina_evaluation_receipt_sha256": fixture["gnina_sha256"],
        "expected_smina_evaluation_receipt_sha256": fixture["smina_sha256"],
    }


def test_comparison_uses_one_all_case_denominator_and_stays_claim_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    receipt = materialize_posebusters_same_input_engine_comparison(
        **_arguments(fixture)  # type: ignore[arg-type]
    )
    payload = receipt.to_dict()

    assert payload["all_case_denominator"] == 3
    assert payload["cases_present_in_every_receipt"] == 2
    assert payload["archive_intake_receipt_sha256"] == _INTAKE
    assert payload["same_input_binding_verified"] is True
    assert payload["all_failure_rows_retained"] is True
    assert payload["pose_generation_performed"] is False
    assert payload["engine_executed_by_this_module"] is False
    assert payload["benchmark_executed"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert list(payload["scientific_blockers"]) == list(
        POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_BLOCKERS
    )

    rows = payload["case_rows"]
    assert isinstance(rows, list)
    assert [row["case_id"] for row in rows] == list(_CASE_IDS)

    absent_row = next(row for row in rows if row["case_id"] == _CASE_IDS[2])
    assert absent_row["gnina"]["status"] == "absent_from_receipt"
    assert absent_row["present_in_every_receipt"] is False
    assert absent_row["engine_ids_present"] == ["internal", "vina", "smina"]

    metrics = {
        (row["engine_id"], row["metric_id"]): row for row in payload["metrics"]
    }
    assert all(row["denominator"] == 3 for row in metrics.values())
    assert metrics[("internal", "top_1_rmsd_hit_rate")]["numerator"] == 1
    assert metrics[("vina", "top_1_rmsd_hit_rate")]["numerator"] == 1
    assert metrics[("gnina", "top_1_rmsd_hit_rate")]["numerator"] == 1
    assert metrics[("smina", "top_1_rmsd_hit_rate")]["numerator"] == 1
    assert metrics[("gnina", "top_1_valid_pose_rate")]["numerator"] == 0
    assert metrics[("internal", "evaluated_case_rate")]["numerator"] == 1

    for row in metrics.values():
        low = float.fromhex(row["confidence_interval_low_binary64_hex"])
        high = float.fromhex(row["confidence_interval_high_binary64_hex"])
        estimate = float.fromhex(row["estimate_binary64_hex"])
        assert 0.0 <= low <= estimate <= high <= 1.0
        assert row["confidence_interval_method"] == "two_sided_wilson_score"


def test_pairwise_top_1_agreement_partitions_every_case(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    payload = materialize_posebusters_same_input_engine_comparison(
        **_arguments(fixture)  # type: ignore[arg-type]
    ).to_dict()
    agreements = {
        row["external_engine_id"]: row
        for row in payload["internal_versus_external_top_1_agreement"]
    }
    assert set(agreements) == {"vina", "gnina", "smina"}
    for row in agreements.values():
        assert row["denominator"] == 3
        assert (
            row["both_top_1_rmsd_hit_case_count"]
            + row["internal_only_top_1_rmsd_hit_case_count"]
            + row["external_only_top_1_rmsd_hit_case_count"]
            + row["neither_top_1_rmsd_hit_case_count"]
            == 3
        )
    assert agreements["vina"]["both_top_1_rmsd_hit_case_count"] == 1
    assert agreements["vina"]["top_1_rmsd_hit_agreement_case_count"] == 3


def test_receipt_reconstructs_exactly_and_refuses_overwrite(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    receipt = materialize_posebusters_same_input_engine_comparison(
        **_arguments(fixture)  # type: ignore[arg-type]
    )
    output = tmp_path / "receipts" / "comparison.json"
    receipt.write_json(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600

    verified = verify_posebusters_same_input_engine_comparison_receipt(
        comparison_receipt_path=output,
        expected_comparison_receipt_sha256=receipt.fingerprint_sha256,
        **_arguments(fixture),  # type: ignore[arg-type]
    )
    assert verified.canonical_bytes() == receipt.canonical_bytes()

    with pytest.raises(
        PoseBustersSameInputEngineComparisonError,
        match="already exists",
    ):
        receipt.write_json(output)

    output.chmod(0o644)
    with pytest.raises(
        PoseBustersSameInputEngineComparisonError,
        match="mode-0600 regular file",
    ):
        verify_posebusters_same_input_engine_comparison_receipt(
            comparison_receipt_path=output,
            expected_comparison_receipt_sha256=receipt.fingerprint_sha256,
            **_arguments(fixture),  # type: ignore[arg-type]
        )


def test_mismatched_archive_intake_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(
        tmp_path,
        intake_overrides={"gnina": hashlib.sha256(b"other-intake").hexdigest()},
    )
    with pytest.raises(
        PoseBustersSameInputEngineComparisonError,
        match="same archive intake",
    ):
        materialize_posebusters_same_input_engine_comparison(
            **_arguments(fixture)  # type: ignore[arg-type]
        )


def test_external_receipt_must_name_its_expected_engine(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    arguments = _arguments(fixture)
    arguments["gnina_evaluation_receipt_path"] = fixture["smina_path"]
    arguments["expected_gnina_evaluation_receipt_sha256"] = fixture["smina_sha256"]
    with pytest.raises(
        PoseBustersSameInputEngineComparisonError,
        match="does not name its expected engine",
    ):
        materialize_posebusters_same_input_engine_comparison(
            **arguments  # type: ignore[arg-type]
        )


def test_claim_open_upstream_receipt_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    path = tmp_path / "claim-open-vina.json"
    payload = _engine_payload(
        schema_id=vina_module.POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID,
        cases=(_case(_CASE_IDS[0], poses=(_pose(rank=1),)),),
    )
    payload["claim_safe"] = True
    digest = _write_receipt(path, payload)
    arguments = _arguments(fixture)
    arguments["vina_evaluation_receipt_path"] = path
    arguments["expected_vina_evaluation_receipt_sha256"] = digest
    with pytest.raises(
        PoseBustersSameInputEngineComparisonError,
        match="must keep claim_safe=false",
    ):
        materialize_posebusters_same_input_engine_comparison(
            **arguments  # type: ignore[arg-type]
        )


def test_cli_materialize_and_verify_round_trip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fixture = _fixture(tmp_path)
    flags = [
        "--internal-oracle-receipt",
        str(fixture["internal_path"]),
        "--vina-evaluation-receipt",
        str(fixture["vina_path"]),
        "--gnina-evaluation-receipt",
        str(fixture["gnina_path"]),
        "--smina-evaluation-receipt",
        str(fixture["smina_path"]),
        "--expected-internal-oracle-receipt-sha256",
        str(fixture["internal_sha256"]),
        "--expected-vina-evaluation-receipt-sha256",
        str(fixture["vina_sha256"]),
        "--expected-gnina-evaluation-receipt-sha256",
        str(fixture["gnina_sha256"]),
        "--expected-smina-evaluation-receipt-sha256",
        str(fixture["smina_sha256"]),
    ]
    output = tmp_path / "cli-comparison.json"
    assert comparison.main(["materialize", *flags, "--output", str(output)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["all_case_denominator"] == 3
    assert summary["claim_safe"] is False

    document = json.loads(output.read_text(encoding="ascii"))
    assert (
        comparison.main(
            [
                "verify",
                *flags,
                "--receipt",
                str(output),
                "--expected-comparison-receipt-sha256",
                document["receipt_sha256"],
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["same_input_binding_verified"] is True


def test_cli_help_describes_the_closed_claim_boundary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        comparison.main(["--help"])
    output = capsys.readouterr().out
    assert "same-input" in output
    assert "closed" in output
