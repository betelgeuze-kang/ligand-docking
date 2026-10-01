"""Synthetic, outcome-free receipt for a completed four-arm CPU comparison."""

import pytest

from tools.analysis import prepared_comparison_readiness as diagnostic
from tools.product import compare_prepared_candidate_ranks as ranks
from tools.product import compare_prepared_candidate_policies as runner
from tests.unit.test_prepared_candidate_comparison import _protocol
from tests.unit.test_candidate_policy_d3 import protocol_fixture as d3_protocol_fixture
from tests.unit.test_prepared_rank_workflow import plan


@pytest.fixture(scope="module")
def synthetic_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("prepared-readiness")
    protocol = _protocol(root / "input", seconds=30)
    ready = ranks.run(protocol, plan(), root / "run")
    return root, ready


def test_synthetic_readiness_separates_requested_prepared_and_scored(synthetic_run):
    root, ready = synthetic_run
    path = root / "readiness.json"
    receipt = diagnostic.report(ready, path)
    value = diagnostic.verify(receipt)
    assert value["source_kind"] == "synthetic_constants"
    assert value["requested_pool_ids"] == list("abcd")
    assert value["prepared_request_present_ids"] == list("abc")
    assert value["prepared_request_missing_ids"] == ["d"]
    assert value["arms"]["similarity"]["scored_ids"] == list("abc")
    assert value["arms"]["engine"]["scored_ids"] == list("ab")
    assert value["arms"]["engine"]["status_ids"]["failed"] == ["c"]
    assert value["arms"]["engine"]["status_ids"]["unsupported"] == ["d"]
    assert value["four_arm_common_scored_ids"] == list("ab")
    assert value["four_arm_common_scored_count"] == 2
    assert value["arms"]["engine"]["observed_cost"]["outer_engine_calls"] == 3
    assert value["arms"]["similarity"]["observed_cost"]["outer_engine_calls"] == 0
    assert value["arms"]["engine"]["observed_cost"]["measured_process_wall_seconds"] > 0
    assert value["arms"]["engine"]["nested_D3_work"]["observed_sums"] is None
    for key in ("same_prepared_assay_state_verified", "heldout_blindness_verified",
                "scientifically_validated", "ai_advantage_claimed"):
        assert value[key] is False
    assert value["eligible_source_state_join_count"] is None
    assert value["upstream_acquisition_preparation_pose_generation_cost"] is None
    assert runner.file_ref(path) == receipt


def test_readiness_refuses_changed_source_or_receipt(synthetic_run, tmp_path):
    root, ready = synthetic_run
    source = root / "run/execution/engine" / (runner.sha("a") + ".row.json")
    original = source.read_bytes()
    receipt = diagnostic.report(ready, tmp_path / "published.json")
    source.write_bytes(original + b" ")
    try:
        with pytest.raises(ValueError, match="readiness_source_or_diagnostic_changed"):
            diagnostic.verify(receipt)
    finally:
        source.write_bytes(original)
    changed_row = runner.read(source)
    changed_row["payload"]["score"] = 999
    source.write_text(runner.canonical(changed_row))
    try:
        output = tmp_path / "never-published.json"
        with pytest.raises(ValueError):
            diagnostic.report(ready, output)
        assert not output.exists()
    finally:
        source.write_bytes(original)
    changed = runner.read(receipt["path"])
    changed["payload"]["four_arm_common_scored_count"] += 1
    damaged = tmp_path / "damaged.json"
    damaged.write_text(runner.canonical(changed))
    with pytest.raises(ValueError, match="invalid_readiness_receipt"):
        diagnostic.verify(runner.file_ref(damaged))


def test_partial_nested_D3_work_is_not_reported_as_total():
    work = dict.fromkeys(diagnostic.D3_WORK, 1)
    rows = [{"record_id": "a", "d3_summary": {"work": work}}, {"record_id": "b"}]
    value = diagnostic._work("engine", rows, {"schema_version": runner.D3_SCHEMA}, 2)
    assert value == {"status": "partial", "observed_candidate_ids": ["a"],
                     "observed_sums": work, "calls_without_observation": 1}
    unknown = diagnostic._work("engine", rows[1:], {"schema_version": runner.D3_SCHEMA}, None)
    assert unknown["observed_sums"] is None
    assert unknown["calls_without_observation"] is None


def test_readiness_reports_only_observed_work_from_real_synthetic_D3_run(tmp_path):
    protocol, _ = d3_protocol_fixture(tmp_path / "input")
    ready = ranks.run(protocol, plan(), tmp_path / "run")
    receipt = diagnostic.report(ready, tmp_path / "d3-readiness.json")
    value = diagnostic.verify(receipt)
    assert value["calculation_backend"] == "fixed_receptor_d3_v1"
    assert value["prepared_request_present_ids"] == ["a", "b"]
    assert value["four_arm_common_scored_ids"] == ["a", "b"]
    engine = value["arms"]["engine"]
    assert engine["nested_D3_work"]["status"] == "complete"
    assert engine["nested_D3_work"]["calls_without_observation"] == 0
    assert engine["nested_D3_work"]["observed_sums"]["actual_force_evaluation_calls"] > 0
    assert engine["observed_cost"]["outer_engine_calls"] == 2
    assert value["eligible_source_state_join_count"] is None


def test_readiness_cli_report_and_verify(synthetic_run, tmp_path, capsys):
    _, ready = synthetic_run
    output = tmp_path / "cli.json"
    assert diagnostic.main(["report", "--ready", ready["path"], "--ready-sha256",
                            ready["sha256"], "--output", str(output)]) == 0
    capsys.readouterr()
    receipt = runner.file_ref(output)
    assert diagnostic.main(["verify", "--report", receipt["path"], "--report-sha256",
                            receipt["sha256"]]) == 0
    assert '"status":"passed"' in capsys.readouterr().out
