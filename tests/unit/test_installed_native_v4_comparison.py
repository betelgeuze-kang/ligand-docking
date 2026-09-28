"""Native v4 source-to-installed-selector and four-arm journal contracts."""

import copy
import json
import shutil

import pytest

from betelgeuze_product import installed_synthetic_comparison as comparison
from betelgeuze_product import installed_native_v4_comparison as native_cli
from betelgeuze_product import installed_native_v4_source as source_verifier
from tools.product import train_public_chembl_selector as checkout_trainer
from tools.product import public_assay_dataset as common
from tools.product import public_chembl_receptor_intake as checkout_intake
from tests.unit.test_public_chembl_receptor_intake import synthetic_intake


@pytest.fixture
def bounded_source(tmp_path):
    manifest, entries = synthetic_intake.__wrapped__(tmp_path)
    source = tmp_path / "intake"
    checkout_intake.build(manifest["path"], manifest["sha256"], source)
    reference = {
        "schema_version": source_verifier.REFERENCE_SCHEMA,
        "input_dir": str(source),
        "summary_sha256": common.file_sha(source / "summary.json"),
        "phase": "fit",
    }
    return tmp_path, source, reference, entries


def _protocol(reference):
    rows, _ = comparison._native_rows(reference)
    pool = [row["record_id"] for row in rows if row["role"] == "development_test"]
    return {
        "schema_version": comparison.NATIVE_PROTOCOL,
        "source": reference,
        "requests": dict.fromkeys(pool),
        "budget_seconds_per_arm": 20.0,
        "max_engine_calls_per_arm": len(pool),
        "arm_order": ["ai_engine", "similarity", "engine", "similarity_engine"],
        "selection_seed": 17,
        "tie_policy": "seeded_pool_order",
    }


def test_native_fit_selector_matches_checkout_trainer(bounded_source, tmp_path):
    _, source, reference, _ = bounded_source
    frozen = comparison.freeze(_protocol(reference))
    assert frozen["source_kind"] == comparison.NATIVE_SOURCE_KIND
    assert frozen["source_verification"]["assigned_role_counts"] == {
        "fit": 6, "calibration": 0, "development_test": 1,
    }
    assert frozen["source_verification"]["evaluation_labels_read"] == 0
    expected = checkout_trainer.fit(
        input_dir=source, summary_sha256=reference["summary_sha256"],
        output_dir=tmp_path / "checkout-fit",
    )
    assert expected["evaluation_label_rows_unread"] == 1
    saved = [json.loads(line) for line in
             (tmp_path / "checkout-fit/predictions-before-evaluation-labels.jsonl")
             .read_text().splitlines()]
    actual = comparison._predictions(frozen, "ai_engine")
    for row in saved:
        if row["record_id"] in frozen["pool"]:
            assert actual[row["record_id"]] == pytest.approx(row["predicted"], rel=1e-12)


def test_native_run_rechecks_source_and_reports_zero_engine_calls(bounded_source, tmp_path):
    _, _, reference, _ = bounded_source
    protocol = _protocol(reference)
    root = tmp_path / "native-run"
    result = comparison.run(protocol, root)
    assert result["schema_version"] == comparison.NATIVE_RESULT
    assert result["source_kind"] == comparison.NATIVE_SOURCE_KIND
    assert result["evaluation_labels_read"] == 0
    assert result["scientifically_validated"] is False
    assert result["pool"] == list(protocol["requests"])
    for arm in comparison.ARMS:
        assert result["arms"][arm]["worker_complete"]["engine_calls"] == 0
        assert result["arms"][arm]["denominator"]["requested"] == len(result["pool"])
    assert comparison.verify_run(protocol, root)["status"] == "verified"
    assert comparison.run(protocol, root, resume=True) == result
    changed = copy.deepcopy(protocol)
    changed["source"]["summary_sha256"] = "0" * 64
    assert comparison.verify_run(changed, root)["status"] == "invalid"
    resealed = tmp_path / "resealed-native"
    shutil.copytree(root, resealed)
    priority_path = resealed / "ai_engine/priority.json"
    priority = json.loads(priority_path.read_text())
    candidate = next(iter(priority["predictions"]))
    priority["predictions"][candidate] += 1.0
    priority_path.write_bytes(comparison._canonical(priority) + b"\n")
    result_path = resealed / "comparison.json"
    altered_result = json.loads(result_path.read_text())
    altered_result["arms"]["ai_engine"]["priority"] = priority
    result_path.write_bytes(comparison._canonical(altered_result) + b"\n")
    assert comparison.verify_run(protocol, resealed)["reason"] == (
        "installed_priority_recalculation_mismatch"
    )


def test_native_protocol_rejects_unlinked_prepared_request(bounded_source):
    _, _, reference, _ = bounded_source
    protocol = _protocol(reference)
    protocol["requests"][next(iter(protocol["requests"]))] = {
        "path": "/unopened/prepared-pose.json", "sha256": "0" * 64,
    }
    with pytest.raises(ValueError, match="native_prepared_candidate_identity_link_not_supported"):
        comparison.freeze(protocol)


def test_native_entry_rejects_synthetic_protocol(tmp_path):
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({"schema_version": comparison.PROTOCOL}))
    with pytest.raises(ValueError, match="native_v4_comparison_requires_native_protocol"):
        native_cli.main(["verify-run", "--protocol", str(protocol),
                         "--run-dir", str(tmp_path / "absent")])
