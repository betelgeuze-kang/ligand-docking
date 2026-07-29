from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.build_engine_v2_solo_self_review import (
    _canonical_bytes,
    _sha256_value,
    _verify_development_source_binding,
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
