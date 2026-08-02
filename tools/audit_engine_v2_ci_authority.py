#!/usr/bin/env python3
"""Build a deterministic inventory of Engine V2 CI authority surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_ID = "betelgeuze.engine_v2_ci_authority_inventory/1.0.0"
AUTHORITATIVE_WORKFLOWS = (
    ".github/workflows/ci-engine-v2-main.yml",
    ".github/workflows/ci-engine-v2-release-candidate.yml",
    ".github/workflows/ci-engine-v2-cpu-reference-validation-protocol.yml",
)
CLEARANCE_ACTIVATION_REQUIRED_TOKENS = (
    "betelgeuze_engine_v2/benchmark/source_paired_clearance_activation.py",
    "betelgeuze_engine_v2/docking/source_paired_clearance_activation.py",
    "config/engine_v2_source_paired_clearance_activation.json",
    "tools/verify_engine_v2_source_paired_clearance_activation.py",
    "tests/unit/test_source_paired_clearance_activation.py",
    "tests/unit/test_source_paired_clearance_activation_evidence.py",
    "tests/unit/test_source_paired_torsion_rescue_activation_snapshot.py",
    "tests/unit/test_verify_engine_v2_source_paired_clearance_activation.py",
    "docs/engine_v2_source_paired_clearance_activation.md",
    "docs/engine_v2_source_paired_clearance_selection_policy.md",
    "docs/engine_v2_stage0_status.md",
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_inventory(repo_root: Path) -> dict[str, Any]:
    workflow_root = repo_root / ".github/workflows"
    workflows = tuple(
        sorted(
            path.relative_to(repo_root).as_posix()
            for path in workflow_root.glob("ci-engine-v2-*.yml")
            if path.is_file()
        )
    )
    authoritative = tuple(path for path in AUTHORITATIVE_WORKFLOWS if path in workflows)
    specialized = tuple(
        path for path in workflows if path not in AUTHORITATIVE_WORKFLOWS
    )
    hashes = {path: _sha256(repo_root / path) for path in workflows}
    main_text = (repo_root / AUTHORITATIVE_WORKFLOWS[0]).read_text(encoding="utf-8")
    stage0_required_tokens = (
        "tools/__init__.py",
        "config/engine_v2_public_redocking_stage0_threshold_evidence.json",
        "tests/unit/test_analyze_engine_v2_score_terms.py",
        "tests/unit/test_engine_v2_blind_stage0.py",
        "tests/unit/test_build_engine_v2_stage0_development_gate_ledger.py",
        "tests/unit/test_classify_engine_v2_stage0_full_suite.py",
        "tests/unit/test_reconcile_engine_v2_stage0_full_suites.py",
        "tools/verify_engine_v2_public_redocking_stage0.py",
        "tools/build_engine_v2_stage0_development_gate_ledger.py",
        "tools/classify_engine_v2_stage0_full_suite.py",
        "tools/reconcile_engine_v2_stage0_full_suites.py",
    ) + CLEARANCE_ACTIVATION_REQUIRED_TOKENS
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "workflow_count": len(workflows),
        "authoritative_workflows": list(authoritative),
        "specialized_workflows": list(specialized),
        "workflow_sha256s": hashes,
        "workflow_inventory_sha256": hashlib.sha256(
            _canonical_bytes(hashes)
        ).hexdigest(),
        "stage0_tests_in_authoritative_main": all(
            token in main_text for token in stage0_required_tokens
        ),
        "new_feature_workflow_policy": "consolidate_into_authoritative_workflows",
        "specialized_workflows_hidden": False,
        "issue_199_external_state_mutated": False,
    }
    payload["receipt_sha256"] = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    payload = build_inventory(arguments.repo_root.resolve())
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(payload["receipt_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
