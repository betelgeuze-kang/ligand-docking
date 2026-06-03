from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_cameo.intake import build_intake_record, persist_intake_record, sequence_records_from_payload


def test_sequence_records_from_cameo_like_payload() -> None:
    records = sequence_records_from_payload(
        {
            "sequences": [{"id": "chain_A", "sequence": "acdef"}],
            "fasta": ">chain_B\nGHIKL\n",
        }
    )

    assert records == [
        {"id": "chain_A", "sequence": "ACDEF"},
        {"id": "chain_B", "sequence": "GHIKL"},
    ]


def test_build_and_persist_intake_record_is_fail_closed(tmp_path: Path) -> None:
    payload = {
        "target_id": "CAMEO_COMPLEX_001",
        "results_email": "team@example.org",
        "sequence": "ACDEFG",
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")

    record = build_intake_record(
        payload=payload,
        raw_request=raw,
        request_method="POST",
        source_host="127.0.0.1",
        capability_lane="polymer_complex_receiver_dry_run",
        job_id="job-001",
    )

    assert record["job_id"] == "job-001"
    assert record["status"] == "received_fail_closed"
    assert record["target_id"] == "CAMEO_COMPLEX_001"
    assert record["results_email_redacted"] == "t***@example.org"
    assert record["parsed_sequence_count"] == 1
    assert record["prediction_generation_enabled"] is False
    assert record["outbound_email_enabled"] is False

    out = persist_intake_record(record, tmp_path / "cameo_jobs")
    assert out.exists()
    stored = json.loads(out.read_text())
    assert stored["claim_boundary"].startswith("CAMEO intake scaffold only")

