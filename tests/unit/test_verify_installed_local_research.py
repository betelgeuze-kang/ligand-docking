"""Source-side checks for the installed workflow receipt inspector."""
from __future__ import annotations

import shutil

import pytest

from betelgeuze_product import local_research_verify, local_research_workflow
from tests.unit.test_local_research_workflow import request
from tools.product.verify_installed_local_research import _check_run_receipts


def test_fresh_and_resumed_receipts_and_tampered_copy(tmp_path):
    prepared = request(tmp_path)
    run = tmp_path / "run"
    assert local_research_workflow.run_workflow(prepared, run_dir=run)["exit_code"] == 0
    assert local_research_workflow.run_workflow(prepared, run_dir=run, resume=True)["exit_code"] == 0
    first = local_research_verify.verify_run(run, attempt=1)
    latest = local_research_verify.verify_run(run)
    receipt = _check_run_receipts(run, first, latest)
    assert [row["attempt"] for row in receipt["attempts"]] == [1, 2]
    assert receipt["restored_rows"] == 2
    assert receipt["newly_completed_rows"] == 0
    assert all(row["summary_receipt_verified"] and row["html_verified"]
               for row in receipt["attempts"])

    copied = tmp_path / "tampered-run"
    shutil.copytree(run, copied)
    html = copied / "attempt-000002/report.html"
    raw = html.read_bytes()
    html.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    rejected = local_research_verify.verify_run(copied)
    assert rejected["status"] == "invalid"
    assert rejected["reason"] == "artifact_digest_mismatch"
    with pytest.raises(ValueError, match="installed_attempt_receipt_mismatch"):
        _check_run_receipts(copied, first, rejected)
    assert local_research_verify.verify_run(run)["status"] == "intact"


def test_missing_summary_receipt_is_not_accepted(tmp_path):
    prepared = request(tmp_path)
    run = tmp_path / "run"
    local_research_workflow.run_workflow(prepared, run_dir=run)
    local_research_workflow.run_workflow(prepared, run_dir=run, resume=True)
    first = local_research_verify.verify_run(run, attempt=1)
    latest = local_research_verify.verify_run(run)
    first["summary_receipt_verified"] = False
    with pytest.raises(ValueError, match="installed_attempt_receipt_mismatch"):
        _check_run_receipts(run, first, latest)
