"""Fresh CSV controls for complete, unambiguous Stage2 manifest handoff."""
from __future__ import annotations

import csv
import pytest

from tools.product.merge_stage2_manifests import merge_stage2_manifests


def _inputs(tmp_path):
    trajectory, inline = tmp_path / "trajectory.csv", tmp_path / "inline.csv"
    trajectory.write_text("queue_id,score\n001,0\n", encoding="utf-8")
    inline.write_text("queue_id,inline_score\nNA,0.0\n", encoding="utf-8")
    return trajectory, inline, tmp_path / "merged.csv"


def test_merge_preserves_identity_zeros_and_missing_terms(tmp_path):
    trajectory, inline, output = _inputs(tmp_path)
    result = merge_stage2_manifests(str(trajectory), str(inline), out_csv=str(output))
    with output.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert rows == [{"queue_id": "001", "score": "0", "inline_score": ""},
                    {"queue_id": "NA", "score": "", "inline_score": "0.0"}]
    assert result["row_count"] == 2


@pytest.mark.parametrize("body", [
    "queue_id,score\n001,0\n001,1\n",  # duplicate within a source
    "queue_id,score\nNA,0\n",  # collision with the other source
    "queue_id,score\n,0\n", "queue_id,score\n   ,0\n",
    "queue_id,queue_id\n001,other\n", "queue_id,score\n001\n",
    "queue_id,score\n001,0,extra\n", "score\n0\n",
])
def test_ambiguous_or_malformed_sources_never_replace_output(tmp_path, body):
    trajectory, inline, output = _inputs(tmp_path)
    trajectory.write_text(body, encoding="utf-8")
    output.write_text("previous-result", encoding="utf-8")
    with pytest.raises(ValueError):
        merge_stage2_manifests(str(trajectory), str(inline), out_csv=str(output))
    assert output.read_text() == "previous-result"


@pytest.mark.parametrize("side", ["trajectory", "inline"])
def test_missing_named_input_is_not_silently_omitted(tmp_path, side):
    trajectory, inline, output = _inputs(tmp_path)
    (trajectory if side == "trajectory" else inline).unlink()
    with pytest.raises(FileNotFoundError):
        merge_stage2_manifests(str(trajectory), str(inline), out_csv=str(output))
    assert not output.exists()


@pytest.mark.parametrize("side", ["trajectory", "inline"])
def test_output_alias_cannot_replace_either_source(tmp_path, side):
    trajectory, inline, _ = _inputs(tmp_path)
    output = trajectory if side == "trajectory" else inline
    before = output.read_bytes()
    with pytest.raises(ValueError, match="distinct"):
        merge_stage2_manifests(str(trajectory), str(inline), out_csv=str(output))
    assert output.read_bytes() == before


@pytest.mark.parametrize("expected_traj,expected_skip", [
    (["missing"], ["NA"]), (["001"], []), (["NA"], ["001"]),
    (["001", "001"], ["NA"]), ("001", ["NA"]), ([None], ["NA"]),
])
def test_expected_partition_coverage_is_exact(tmp_path, expected_traj, expected_skip):
    trajectory, inline, output = _inputs(tmp_path)
    with pytest.raises(ValueError):
        merge_stage2_manifests(str(trajectory), str(inline), out_csv=str(output),
                              expected_traj_queue_ids=expected_traj,
                              expected_skip_queue_ids=expected_skip)
    assert not output.exists()


def test_exact_coverage_preserves_failed_candidate_rows_and_hashes(tmp_path):
    import hashlib
    trajectory, inline, output = _inputs(tmp_path)
    trajectory.write_text("queue_id,status,reason\n001,failed,numerical_failure\n")
    result = merge_stage2_manifests(str(trajectory), str(inline), out_csv=str(output),
                                   expected_traj_queue_ids=["001"], expected_skip_queue_ids=["NA"])
    assert result["queue_coverage_validated"] is True
    assert result["row_count"] == 2
    with output.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["status"] == "failed"
    assert rows[0]["reason"] == "numerical_failure"
    assert result["traj_manifest_sha256"] == hashlib.sha256(trajectory.read_bytes()).hexdigest()
    assert result["skip_manifest_sha256"] == hashlib.sha256(inline.read_bytes()).hexdigest()
    assert result["merged_manifest_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


@pytest.mark.parametrize("expected", ["", 0, False])
def test_absent_partition_still_validates_expected_identity_type(tmp_path, expected):
    _, inline, output = _inputs(tmp_path)
    with pytest.raises(ValueError):
        merge_stage2_manifests("", str(inline), out_csv=str(output),
                              expected_traj_queue_ids=expected, expected_skip_queue_ids=["NA"])
    assert not output.exists()


def test_explicit_empty_partition_allows_complete_other_partition(tmp_path):
    _, inline, output = _inputs(tmp_path)
    result = merge_stage2_manifests("", str(inline), out_csv=str(output),
                                   expected_traj_queue_ids=[], expected_skip_queue_ids=["NA"])
    assert result["row_count"] == 1
    assert result["queue_coverage_validated"] is True


@pytest.mark.parametrize("module_name", ["tools.product.generate_ligand_trajectory_batch",
                                        "tools.generate_ligand_trajectory_engine"])
def test_actual_producer_reader_preserves_literal_ids_before_any_compute(tmp_path, monkeypatch, module_name):
    import argparse
    import importlib
    module = importlib.import_module(module_name)
    source = tmp_path / "queue.csv"
    source.write_text("queue_id,affinity_hint\n001,0\nNA,\n")
    original_read = module.pd.read_csv
    observed = {}

    class StopBeforeCompute(Exception):
        pass

    def read_then_stop(*args, **kwargs):
        frame = original_read(*args, **kwargs)
        observed["ids"] = frame["queue_id"].tolist()
        observed["zero"] = frame["affinity_hint"].iloc[0]
        observed["missing"] = module.pd.isna(frame["affinity_hint"].iloc[1])
        raise StopBeforeCompute

    monkeypatch.setattr(module.pd, "read_csv", read_then_stop)
    with pytest.raises(StopBeforeCompute):
        module.run_batch(argparse.Namespace(queue_csv=str(source)))
    assert observed["ids"] == ["001", "NA"]
    assert observed["zero"] == 0.
    assert observed["missing"]
