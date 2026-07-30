from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.build_engine_v2_solo_self_review import (
    _canonical_bytes,
    _sha256_value,
    _verify_development_source_binding,
)
from tools.build_engine_v2_solo_stage0_policy import (
    OPERATIONAL_SCHEMA_ID,
    SELF_REVIEW_SCHEMA_ID,
    THRESHOLD_SCHEMA_ID,
    _verify_review_chain,
)


def _write_receipt(
    root: Path,
    *,
    engine_id: str,
    case_id: str,
    implementation_sha256: str,
    runner_id: str,
) -> tuple[str, str]:
    path = root / "receipts" / engine_id / f"{case_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "implementation_sha256": implementation_sha256,
        "runner_id": runner_id,
        "result": {"engine_id": engine_id, "case_id": case_id},
    }
    payload["receipt_sha256"] = _sha256_value(payload)
    encoded = _canonical_bytes(payload) + b"\n"
    path.write_bytes(encoded)
    return path.relative_to(root).as_posix(), hashlib.sha256(encoded).hexdigest()


def _write_self_hashed(path: Path, payload: dict[str, object], field: str) -> None:
    payload[field] = _sha256_value(payload)
    path.write_bytes(_canonical_bytes(payload) + b"\n")


def _evidence(root: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    implementation = "a" * 64
    runner = "runner/1"
    source_rows: dict[str, str] = {}
    development_rows: dict[str, str] = {}
    for engine_id in ("engine_v2", "vina", "gnina"):
        for case_id in ("case-a", "case-b"):
            path, digest = _write_receipt(
                root,
                engine_id=engine_id,
                case_id=case_id,
                implementation_sha256=(
                    implementation if engine_id == "engine_v2" else "b" * 64
                ),
                runner_id=runner,
            )
            source_rows[path] = digest
            if engine_id == "engine_v2":
                development_rows[path] = digest
    case_ids = ["case-a", "case-b"]
    operational = {
        "source_state": {
            "engine_implementation_sha256": implementation,
            "runner_id": runner,
        }
    }
    development = {
        "source_receipts_sha256": development_rows,
        "case_ids": case_ids,
    }
    threshold = {
        "source_reports_sha256": source_rows,
        "case_count": len(case_ids),
        "case_ids_sha256": _sha256_value(case_ids),
    }
    return operational, development, threshold


def test_development_source_binding_requires_complete_three_engine_case_set(
    tmp_path: Path,
) -> None:
    operational, development, threshold = _evidence(tmp_path)

    assert _verify_development_source_binding(
        repo_root=tmp_path,
        operational=operational,
        development=development,
        threshold=threshold,
    ) == ("a" * 64, "runner/1")

    sources = dict(threshold["source_reports_sha256"])
    sources.pop("receipts/gnina/case-b.json")
    threshold["source_reports_sha256"] = sources
    with pytest.raises(ValueError, match="complete three-engine"):
        _verify_development_source_binding(
            repo_root=tmp_path,
            operational=operational,
            development=development,
            threshold=threshold,
        )


def test_review_chain_binds_pass1_and_rejects_failed_gate(tmp_path: Path) -> None:
    operational_path = tmp_path / "operational.json"
    threshold_path = tmp_path / "threshold.json"
    pass1_path = tmp_path / "pass1.json"
    pass2_path = tmp_path / "pass2.json"
    operational = {
        "schema_id": OPERATIONAL_SCHEMA_ID,
        "developer_id": "solo",
    }
    threshold = {"schema_id": THRESHOLD_SCHEMA_ID}
    _write_self_hashed(operational_path, operational, "receipt_sha256")
    _write_self_hashed(threshold_path, threshold, "evidence_sha256")
    reviewed = {
        "operational_evidence_file_sha256": hashlib.sha256(
            operational_path.read_bytes()
        ).hexdigest(),
        "threshold_evidence_file_sha256": hashlib.sha256(
            threshold_path.read_bytes()
        ).hexdigest(),
    }
    pass1 = {
        "schema_id": SELF_REVIEW_SCHEMA_ID,
        "review_pass": 1,
        "developer_id": "solo",
        "reviewed_at_utc": "2026-07-29T00:00:00Z",
        "reviewed_evidence": reviewed,
        "fresh_internal_blind_holdout_executed": False,
    }
    _write_self_hashed(pass1_path, pass1, "receipt_sha256")
    pass2 = {
        "schema_id": SELF_REVIEW_SCHEMA_ID,
        "review_pass": 2,
        "developer_id": "solo",
        "reviewed_at_utc": "2026-07-30T00:00:00Z",
        "reviewed_evidence": reviewed,
        "previous_review_pass": {
            "path": "pass1.json",
            "file_sha256": hashlib.sha256(pass1_path.read_bytes()).hexdigest(),
            "receipt_sha256": pass1["receipt_sha256"],
            "reviewed_at_utc": pass1["reviewed_at_utc"],
        },
        "development_gate_results": {"proposal_oracle_2a_recovery": "pass"},
        "fresh_internal_blind_holdout_executed": False,
    }
    _write_self_hashed(pass2_path, pass2, "receipt_sha256")

    _, _, observed_pass1, observed_pass2 = _verify_review_chain(
        repo_root=tmp_path,
        operational_path=operational_path,
        threshold_path=threshold_path,
        pass1_path=pass1_path,
        pass2_path=pass2_path,
        developer_id="solo",
    )
    assert observed_pass1["receipt_sha256"] == pass1["receipt_sha256"]
    assert observed_pass2["receipt_sha256"] == pass2["receipt_sha256"]

    pass2.pop("receipt_sha256")
    pass2["development_gate_results"] = {
        "proposal_oracle_2a_recovery": "fail"
    }
    _write_self_hashed(pass2_path, pass2, "receipt_sha256")
    with pytest.raises(ValueError, match="development gates"):
        _verify_review_chain(
            repo_root=tmp_path,
            operational_path=operational_path,
            threshold_path=threshold_path,
            pass1_path=pass1_path,
            pass2_path=pass2_path,
            developer_id="solo",
        )
