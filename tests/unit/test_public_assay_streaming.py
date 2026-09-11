"""Chunk and disk-spool regression tests using real synthetic model inference."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import tracemalloc

import numpy as np
import pytest

from betelgeuze_engine.product import public_assay_selector_shadow as owner
from betelgeuze_engine.product import public_assay_streaming as streaming
from tests.unit.test_public_assay_selector_shadow import _checkpoint, _row, _sidecar


@pytest.mark.parametrize("chunk", [1, 2, 7, 256, 4096])
def test_chunks_match_old_full_batch_and_independent_dot(tmp_path, monkeypatch, chunk):
    coefficients = np.random.default_rng(52).normal(size=1024).tolist()
    path, digest = _checkpoint(tmp_path, monkeypatch, lambda p: p.update(coefficients=coefficients))
    model = owner.load_public_assay_selector(path, expected_sha256=digest)
    rows = [_row(smiles=s, ligand_id=str(i)) for i, s in enumerate(
        ["CCCCC", "c1ccccc1", "CCCCCC", "", "[Zn+2]", "CCCCN", "CCCCC"] * 9)]
    before = json.dumps(rows, sort_keys=True)
    legacy = model._predict_batch(rows)
    actual = model.predict_rows(rows, chunk_size=chunk)
    assert len(actual) == len(rows)
    for old, new, row in zip(legacy, actual, rows):
        old, new = dict(old), dict(new)
        left, right = old.pop("predicted_negative_log10_molar_IC50"), new.pop("predicted_negative_log10_molar_IC50")
        assert old == new
        if left is None:
            assert right is None
        else:
            expected = math.fsum(float(a) * b for a, b in zip(model._fingerprint(row), coefficients)) + 1.5
            assert right == pytest.approx(expected, abs=1e-12, rel=1e-12)
            assert right == pytest.approx(left, abs=1e-12, rel=1e-12)
    assert json.dumps(rows, sort_keys=True) == before


@pytest.mark.parametrize("chunk", [0, -1, True, 1.5, 4097])
def test_invalid_chunk_is_rejected_before_fingerprinting(tmp_path, monkeypatch, chunk):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    model = owner.load_public_assay_selector(path, expected_sha256=digest)
    monkeypatch.setattr(model, "_fingerprint", lambda _: pytest.fail("bad chunk reached chemistry"))
    with pytest.raises(ValueError, match="chunk_size"):
        model.predict_rows([_row()], chunk_size=chunk)


def test_iterable_reads_only_one_batch_ahead_and_bounds_matrix(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    model = owner.load_public_assay_selector(path, expected_sha256=digest)
    consumed, sizes = [], []
    def source():
        for i in range(29):
            consumed.append(i)
            yield _row(ligand_id=str(i))
    original = model._predict_batch
    def observe(rows):
        sizes.append(len(rows))
        return original(rows)
    monkeypatch.setattr(model, "_predict_batch", observe)
    iterator = model.iter_prediction_rows(source(), chunk_size=7)
    assert consumed == []
    assert next(iterator)["row_index"] == 0
    assert len(consumed) == 7
    rest = list(iterator)
    assert [r["row_index"] for r in rest] == list(range(1, 29))
    assert sizes == [7, 7, 7, 7, 1]


@pytest.mark.parametrize("chunk", [1, 3, 256])
def test_real_sidecar_preserves_rows_multiline_bom_and_bad_width(tmp_path, monkeypatch, chunk):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    source = tmp_path / "input.csv"
    header = list(_row()) + ["source_note"]
    cells = [list(_row(ligand_id=x, smiles=s).values()) + ["quoted\nmetadata"]
             for x, s in [("001", "CCCCC"), ("NA", ""), ("001", "c1ccccc1")]]
    cells += [[], ["bad", "width"]]
    with source.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(cells)
    summary, output, _ = _sidecar(tmp_path, path, digest, [_row()],
                                  ligand_csv=str(source), chunk_size=chunk)
    payload = json.loads(output.read_text())
    assert summary["requested_rows"] == 5 and summary["evaluated_rows"] == 2
    assert summary["unsupported_rows"] == 3
    assert [r["input_cells"] for r in payload["rows"]] == cells
    assert [r["row_index"] for r in payload["rows"]] == list(range(5))
    assert summary["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert payload["rows"][0]["ligand_id"] == "001"
    assert payload["rows"][1]["ligand_id"] == "NA"
    assert payload["customer_execution"] is payload["product_ranking_enabled"] is False


@pytest.mark.parametrize("bad_suffix", ['"unterminated', 'x' * (streaming.MAX_RECORD_CHARS + 2), ','.join(['x'] * 257)])
def test_late_invalid_record_never_publishes_successful_prefix(tmp_path, monkeypatch, bad_suffix):
    checkpoint, digest = _checkpoint(tmp_path, monkeypatch)
    source = tmp_path / "bad.csv"
    with source.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(_row()))
        writer.writeheader()
        for _ in range(10):
            writer.writerow(_row())
        stream.write(bad_suffix)
    summary, output, _ = _sidecar(tmp_path, checkpoint, digest, [_row()],
                                  ligand_csv=str(source), chunk_size=2)
    assert summary["status"] == "not_evaluated"
    assert summary["requested_rows"] is None
    assert json.loads(output.read_text())["rows"] == []
    assert summary["reason"].startswith("input_unavailable:")


def test_late_predictor_exception_marks_whole_input_unsupported(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    original = owner.PublicAssaySelectorShadow._predict_batch
    calls = []
    def fail_second(self, rows):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("synthetic late failure")
        return original(self, rows)
    monkeypatch.setattr(owner.PublicAssaySelectorShadow, "_predict_batch", fail_second)
    summary, output, _ = _sidecar(tmp_path, path, digest, [_row()] * 9, chunk_size=2)
    data = json.loads(output.read_text())
    assert summary["requested_rows"] == summary["unsupported_rows"] == 9
    assert summary["evaluated_rows"] == 0
    assert all(r["reason"].startswith("model_unavailable:RuntimeError") for r in data["rows"])
    assert all(r["predicted_negative_log10_molar_IC50"] is None for r in data["rows"])


def test_input_change_during_inference_rejects_whole_sidecar(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    original = owner.PublicAssaySelectorShadow._predict_batch
    def mutate(self, rows):
        (tmp_path / "requests.csv").write_text("changed input")
        return original(self, rows)
    monkeypatch.setattr(owner.PublicAssaySelectorShadow, "_predict_batch", mutate)
    summary, output, _ = _sidecar(tmp_path, path, digest, [_row()] * 5, chunk_size=2)
    assert summary["status"] == "not_evaluated"
    assert "csv_source_changed_during_prediction" in summary["reason"]
    assert json.loads(output.read_text())["rows"] == []


def test_failed_atomic_publish_keeps_previous_sidecar_and_no_temp(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    output = tmp_path / "shadow.json"
    output.write_text("previous complete result")
    def fail(*_):
        raise OSError("synthetic full disk")
    monkeypatch.setattr(streaming.os, "replace", fail)
    summary, _, _ = _sidecar(tmp_path, path, digest, [_row()])
    assert summary["sidecar_status"] == "failed"
    assert output.read_text() == "previous complete result"
    assert not list(tmp_path.glob("shadow.json.*"))


def test_real_inference_has_bounded_working_memory_for_more_rows(tmp_path, monkeypatch):
    path, digest = _checkpoint(tmp_path, monkeypatch)
    # Warm up native fingerprint machinery before observing Python allocations.
    owner.load_public_assay_selector(path, expected_sha256=digest).predict_rows([_row()])
    peaks = []
    for count in (256, 4096):
        source = tmp_path / f"rows-{count}.csv"
        with source.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(_row()))
            writer.writeheader()
            for _ in range(count):
                writer.writerow(_row())
        tracemalloc.start()
        result = owner.run_pre_docking_shadow(
            ligand_csv=str(source), ligand_sdf="", docking_request_json="", resume_stage3_only=False,
            checkpoint=str(path), checkpoint_sha256=digest, output_json=str(tmp_path / f"{count}.json"),
            chunk_size=32)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert result["evaluated_rows"] == count
        assert "rows" not in result
        peaks.append(peak)
    # This measures Python working allocations, not total process RSS/VRAM.
    assert peaks[1] < peaks[0] + 2 * 1024 * 1024, peaks
