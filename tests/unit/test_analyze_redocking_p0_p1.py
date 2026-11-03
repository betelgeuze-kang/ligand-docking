from copy import deepcopy
import pytest
from tools.analyze_redocking_p0_p1 import (
    compare_pair,
    scientific_projection,
    sdf_hashes,
)


def receipt():
    return {
        "input_sha256s": {"native": "a" * 64},
        "evaluation_pipeline_sha256": "b" * 64,
        "implementation_sha256": "c" * 64,
        "result": {
            "status": "success",
            "runtime_seconds": 30.0,
            "execution_command": ["/first"],
            "rmsd_angstroms": [0.0, 1.0],
            "geometric_valid": [True, True],
            "engine_v2_diagnostics": {
                "diagnostic_evaluation_seconds": 42.0,
                "candidates": [
                    {"score": 1.0, "coordinate_fingerprint_sha256": "a" * 64}
                ],
            },
        },
    }


def test_only_operational_changes_are_ignored():
    left, right = receipt(), receipt()
    right["result"]["runtime_seconds"] = 12.0
    right["result"]["execution_command"] = ["/second"]
    right["result"]["engine_v2_diagnostics"]["diagnostic_evaluation_seconds"] = 15.0
    assert compare_pair(left, right)["matches"]


@pytest.mark.parametrize("change", ["bit", "zero", "coordinate", "validity"])
def test_scientific_changes_are_detected(change):
    left, right = receipt(), receipt()
    row = right["result"]
    if change == "bit":
        row["rmsd_angstroms"][1] = float.fromhex("0x1.0000000000001p+0")
    elif change == "zero":
        row["rmsd_angstroms"][0] = -0.0
    elif change == "coordinate":
        row["engine_v2_diagnostics"]["candidates"][0][
            "coordinate_fingerprint_sha256"
        ] = "b" * 64
    else:
        row["geometric_valid"][1] = False
    assert not compare_pair(left, right)["matches"]


def test_partial_results_do_not_pass():
    with pytest.raises(RuntimeError, match="missing"):
        compare_pair(receipt(), None)
    failed = receipt()
    failed["result"]["status"] = "failure"
    with pytest.raises(RuntimeError, match="successful"):
        compare_pair(receipt(), failed)


def test_projection_preserves_raw_result():
    row = receipt()["result"]
    before = deepcopy(row)
    scientific_projection(row)
    assert row == before


def test_sdf_truncation_and_title_identity(tmp_path):
    path = tmp_path / "poses.sdf"
    path.write_bytes(b"title\nrecord\n$$$$\n")
    before = sdf_hashes(path)
    path.write_bytes(b"other\nrecord\n$$$$\n")
    assert before != sdf_hashes(path)
    path.write_bytes(b"title\nrecord\n")
    with pytest.raises(RuntimeError, match="unterminated"):
        sdf_hashes(path)


def test_missing_engine_and_missing_case_remain_in_full_denominator():
    from tools.analyze_redocking_p0_p1 import summarize_rows

    successful = {
        "status": "success",
        "failure_code": "",
        "rmsd_angstroms": [1.0] * 5,
        "geometric_valid": [True] * 5,
        "chemical_valid": [True] * 5,
    }
    failed = {
        "status": "failure",
        "failure_code": "typed_failure",
        "rmsd_angstroms": [],
        "geometric_valid": [],
        "chemical_valid": [],
    }
    records = {
        "one": {
            "engines": {
                "engine_v2": {
                    "row": None,
                    "operation_status": "timeout",
                    "execution": None,
                },
                "vina": {
                    "row": successful,
                    "operation_status": "completed",
                    "execution": None,
                },
                "gnina": {
                    "row": failed,
                    "operation_status": "completed",
                    "execution": None,
                },
            }
        }
    }
    result = summarize_rows(records, ["one", "two", "three"])
    assert result["engine_v2"]["unobserved_rows"] == 3
    assert result["vina"]["counts"]["valid_top1"] == 1
    assert result["vina"]["rates"]["valid_top1"] == 1 / 3
    assert result["gnina"]["typed_failure_rows"] == 1
    assert result["gnina"]["unobserved_rows"] == 2


def test_journal_retains_open_stage_and_detects_earlier_event_tampering(tmp_path):
    from tools.redocking_isolation import AtomicJournal, digest_json
    from tools.analyze_redocking_p0_p1 import journal_observations
    import json

    journal = AtomicJournal(tmp_path / "journal", {"case_id": "fixture"})
    journal.emit({"stage": "prepare", "phase": "start"})
    journal.emit({"stage": "prepare", "phase": "complete", "elapsed_seconds": 1.0})
    journal.emit({"stage": "evaluation", "phase": "start"})
    observed = journal_observations(tmp_path)
    assert observed[0]["event_count"] == 3
    assert observed[0]["unfinished_stages"][0]["stage"] == "evaluation"
    path = tmp_path / "journal/event-000001.json"
    value = json.loads(path.read_text())
    value["event"]["stage"] = "modified"
    value["event_sha256"] = digest_json(
        {k: v for k, v in value.items() if k != "event_sha256"}
    )
    path.write_text(json.dumps(value))
    with pytest.raises(RuntimeError, match="chain"):
        journal_observations(tmp_path)


def test_controller_invalid_receipt_remains_unobserved(tmp_path, monkeypatch):
    import json
    from tools import analyze_redocking_p0_p1 as analysis

    manifest = json.loads(analysis.MANIFEST.read_text())
    cid = manifest["case_ids"][2]
    missing = {
        "row": None,
        "observation_status": "invalid",
        "operation_status": "worker_failed",
        "execution": None,
        "errors": ["original receipt validation failed"],
    }
    summary = {
        "stage": "development",
        "profile": "development_observation_v1",
        "analysis_scope": "contaminated_development",
        "claim_safe": False,
        "source": {},
        "expected_indices": [2],
        "attempted_cases": 1,
        "execution_complete": False,
        "scientific_accuracy_complete": False,
        "fatal_error": None,
        "cases": [
            {
                "case_id": cid,
                "global_index": 2,
                "seed": manifest["seed_base"] + 2,
                "materialization": {},
                "engines": {e: dict(missing) for e in analysis.ENGINES},
            }
        ],
    }
    (tmp_path / "summary.json").write_text(json.dumps(summary))
    monkeypatch.setattr(
        analysis,
        "find_receipt",
        lambda *a: pytest.fail("invalid raw receipt must remain unobserved"),
    )
    result = {}
    analysis.collect_development(tmp_path, result)
    assert all(
        x["row"] is None and x["errors"] for x in result[cid]["engines"].values()
    )


def test_missing_reference_comparison_or_fatal_shard_cannot_claim_complete(tmp_path):
    from tools.analyze_redocking_p0_p1 import finalize_aggregate

    complete_env = {
        "start": {"content_identity_sha256": "a" * 64},
        "end": {},
        "end_comparison": {"matches": True},
        "reference_comparison": {"matches": True},
        "native_runtime_identity_sha256": "b" * 64,
        "native_wheel_manifest_identity_sha256": "c" * 64,
    }
    # End snapshot must be nonempty; it is metadata here, not a forged raw snapshot.
    complete_env["end"] = {"content_identity_sha256": "a" * 64}
    envs = [
        {
            **deepcopy(complete_env),
            "role": "bootstrap_reference",
            "reference_comparison": None,
        }
    ]
    envs += [{**deepcopy(complete_env), "role": "worker_comparison"} for _ in range(4)]
    row = {
        "status": "failure",
        "failure_code": "fixture",
        "rmsd_angstroms": [],
        "geometric_valid": [],
        "chemical_valid": [],
        "engine_v2_diagnostics": {
            "candidates": [],
            "diagnostic_evaluation_seconds": 0.0,
        },
    }
    ids = [str(i) for i in range(34)]
    records = {
        cid: {
            "engines": {
                engine: {
                    "row": deepcopy(row),
                    "operation_status": "completed",
                    "execution": None,
                }
                for engine in ("engine_v2", "vina", "gnina")
            }
        }
        for cid in ids[2:]
    }
    shard = {
        "execution_complete": True,
        "scientific_accuracy_complete": True,
        "fatal_error": None,
    }
    report = {
        "environments": envs,
        "paired_admission": {"paired_ready": True},
        "shards": [
            {**shard, "expected_indices": list(range(start, start + 8))}
            for start in (2, 10, 18, 26)
        ],
    }
    manifest = {"case_ids": ids, "development_indices": list(range(2, 34))}
    report["environments"][1]["reference_comparison"] = None
    finalize_aggregate(report, records, manifest, tmp_path)
    assert not report["environment_verification_complete"]
    assert not report["scientific_accuracy_complete"]
    report["environments"][1]["reference_comparison"] = {"matches": True}
    report["shards"][0]["fatal_error"] = {
        "message": "source changed after last receipt"
    }
    finalize_aggregate(report, records, manifest, tmp_path)
    assert report["environment_verification_complete"]
    assert not report["scientific_accuracy_complete"]


def test_unrelated_invalid_receipt_does_not_abort_other_case_lookup(tmp_path):
    from tools.analyze_redocking_p0_p1 import find_receipt

    bad = tmp_path / "cases/unrelated/engines/engine_v2/receipt.json"
    bad.parent.mkdir(parents=True)
    bad.write_text("{incomplete")
    assert find_receipt(tmp_path, "5SD5_HWI", "engine_v2") is None
