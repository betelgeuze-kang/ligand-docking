#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/ai_md_contract_source_of_truth_gate_current.json"
DEFAULT_OUT_CSV = "runs/ai_md_contract_source_of_truth_gate_current.csv"
DEFAULT_OUT_MD = "runs/ai_md_contract_source_of_truth_gate_current.md"

CLAIM_BOUNDARY = (
    "AI-MD contract source-of-truth gate only; it checks local typed contract, API evidence-bundle, "
    "and reference-oracle surfaces. It does not run docking, execute GPU jobs, promote model outputs, "
    "widen accuracy claims, assemble customer delivery bundles, or mutate external state."
)

REQUIRED_SOURCE_FILES = [
    "pyproject.toml",
    "api/job_store.py",
    "api/main.py",
    "api/models.py",
    "api/validated_runner.py",
    "api/worker.py",
    "betelgeuze_ai_md/__init__.py",
    "betelgeuze_ai_md/contracts/__init__.py",
    "betelgeuze_ai_md/contracts/api_adapter.py",
    "betelgeuze_ai_md/contracts/backmapping_adapter.py",
    "betelgeuze_ai_md/contracts/interaction_adapter.py",
    "betelgeuze_ai_md/contracts/topology_adapter.py",
    "betelgeuze_ai_md/contracts/claim_scope.py",
    "betelgeuze_ai_md/contracts/input_schema.py",
    "betelgeuze_ai_md/contracts/output_schema.py",
    "betelgeuze_ai_md/contracts/verdict_schema.py",
    "betelgeuze_ai_md/contracts/manifest.py",
    "betelgeuze_ai_md/contracts/serialization.py",
    "betelgeuze_ai_md/coarse_md/__init__.py",
    "betelgeuze_ai_md/coarse_md/numpy_ref.py",
    "tools/product/validate_api_runner_profiles.py",
    "tests/unit/test_api_job_store.py",
    "tests/unit/test_api_validated_runner_adapter.py",
    "tests/unit/test_betelgeuze_ai_md_contracts.py",
    "tests/unit/test_betelgeuze_ai_md_api_adapter.py",
    "tests/unit/test_betelgeuze_ai_md_backmapping_interaction_adapters.py",
    "tests/unit/test_betelgeuze_ai_md_topology_adapter.py",
    "tests/unit/test_betelgeuze_ai_md_numpy_ref.py",
]


def _resolve(path_like: str | Path, *, root: Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row(
    *,
    check_id: str,
    category: str,
    passed: bool,
    observed: str,
    required: str,
    artifact_paths: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "category": category,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "artifact_paths": artifact_paths or [],
        "artifact_path_count": len(artifact_paths or []),
        "release_blocker": not passed,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _safe_check(check: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return check()
    except Exception as exc:
        return _row(
            check_id=getattr(check, "__name__", "unknown_check").removeprefix("_check_"),
            category="runtime_exception",
            passed=False,
            observed=f"{type(exc).__name__}: {exc}",
            required="check completes without exception",
        )


def _check_required_source_files(root: Path, required_source_files: list[str]) -> dict[str, Any]:
    missing = [path for path in required_source_files if not _resolve(path, root=root).is_file()]
    digest = hashlib.sha256()
    for path in required_source_files:
        resolved = _resolve(path, root=root)
        digest.update(path.encode("utf-8"))
        digest.update(_sha256_file(resolved).encode("utf-8"))
    return _row(
        check_id="required_source_files_present",
        category="contract_source_files",
        passed=not missing,
        observed=f"required={len(required_source_files)};missing={len(missing)}",
        required="all AI-MD contract, API adapter, reference oracle, and focused test files exist",
        artifact_paths=required_source_files,
    ) | {
        "missing_source_files": missing,
        "missing_source_file_count": len(missing),
        "source_set_sha256": digest.hexdigest(),
    }


def _check_pyproject_package_discovery(root: Path) -> dict[str, Any]:
    pyproject = _resolve("pyproject.toml", root=root)
    text = pyproject.read_text(encoding="utf-8") if pyproject.is_file() else ""
    required_fragment = '"betelgeuze_ai_md*"'
    passed = required_fragment in text
    return _row(
        check_id="pyproject_package_discovery",
        category="contract_source_files",
        passed=passed,
        observed=f"betelgeuze_ai_md_package_glob_present={passed}",
        required='pyproject package discovery includes "betelgeuze_ai_md*"',
        artifact_paths=["pyproject.toml"],
    )


def _check_contract_symbols_exported() -> dict[str, Any]:
    import betelgeuze_ai_md.contracts as contracts

    required_symbols = [
        "MolecularProject",
        "MolecularSystem",
        "CoarseState",
        "TrajectorySummary",
        "BackmappedPose",
        "InteractionEvidence",
        "InteractionReport",
        "AIResidualReport",
        "TopologyValidityReport",
        "Verdict",
        "EvidenceBundle",
        "build_api_evidence_bundle",
        "build_backmapped_pose",
        "build_interaction_report",
        "build_topology_validity_report",
        "write_api_evidence_bundle",
        "fail_closed_topology_report",
    ]
    missing = [symbol for symbol in required_symbols if not hasattr(contracts, symbol)]
    return _row(
        check_id="contract_symbols_exported",
        category="contract_layer",
        passed=not missing,
        observed=f"required_symbols={len(required_symbols)};missing={len(missing)}",
        required="contract package exports all required input, output, verdict, bundle, and API adapter symbols",
    ) | {"missing_symbols": missing, "missing_symbol_count": len(missing)}


def _check_claim_widening_guard() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts import GENERAL_MD_ACCURACY_CLAIM, TOPOLOGY_FIDELITY_SEQUENCE_MAPPED, Verdict
    from betelgeuze_ai_md.contracts.errors import ContractValidationError

    blocked = False
    try:
        Verdict(
            claim_safe=False,
            verdict_label="blocked",
            topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            accuracy_claim_grade=GENERAL_MD_ACCURACY_CLAIM,
        )
    except ContractValidationError:
        blocked = True
    return _row(
        check_id="claim_widening_guard",
        category="claim_boundary",
        passed=blocked,
        observed=f"general_md_accuracy_claim_blocked={blocked}",
        required="general-MD-accuracy promotion remains forbidden by contract validation",
    )


def _check_topology_validity_contract_surface() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts import (
        CLAIM_SCOPE_RESTRICTED_LOCAL,
        EvidenceBundle,
        TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
        TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        TopologyValidityReport,
        Verdict,
        fail_closed_topology_report,
    )
    from betelgeuze_ai_md.contracts.errors import ContractValidationError
    from betelgeuze_ai_md.contracts.output_schema import AIResidualReport, BackmappedPose, InteractionReport, TrajectorySummary

    placeholder_blocked = False
    try:
        EvidenceBundle(
            bundle_id="topology_blocked",
            project_id="topology_blocked",
            ranked_shortlist=[],
            trajectory_summary=TrajectorySummary(frame_count=0),
            backmapped_poses=[],
            interaction_report=InteractionReport(),
            topology_report=TopologyValidityReport(
                status="pass",
                topology_fidelity=TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
            ),
            ai_residual_report=AIResidualReport(),
            failure_flags=[],
            source_hashes={
                "input_hash": "i" * 64,
                "config_hash": "c" * 64,
                "model_hash": "m" * 64,
                "executable_hash": "e" * 64,
            },
            viewer_assets=[],
            wetlab_handoff_table=[],
            verdict=Verdict(
                claim_safe=True,
                verdict_label="delivery_ready",
                claim_scope=CLAIM_SCOPE_RESTRICTED_LOCAL,
                topology_fidelity=TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
            ),
        )
    except ContractValidationError as exc:
        placeholder_blocked = "non-placeholder topology fidelity" in str(exc)

    blocker_blocked = False
    try:
        EvidenceBundle(
            bundle_id="topology_blocker",
            project_id="topology_blocker",
            ranked_shortlist=[],
            trajectory_summary=TrajectorySummary(frame_count=0),
            backmapped_poses=[],
            interaction_report=InteractionReport(),
            topology_report=TopologyValidityReport(
                status="pass",
                topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
                claim_blockers=["sequence_mapping_unresolved"],
            ),
            ai_residual_report=AIResidualReport(),
            failure_flags=[],
            source_hashes={
                "input_hash": "i" * 64,
                "config_hash": "c" * 64,
                "model_hash": "m" * 64,
                "executable_hash": "e" * 64,
            },
            viewer_assets=[],
            wetlab_handoff_table=[],
            verdict=Verdict(
                claim_safe=True,
                verdict_label="delivery_ready",
                claim_scope=CLAIM_SCOPE_RESTRICTED_LOCAL,
                topology_fidelity=TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            ),
        )
    except ContractValidationError as exc:
        blocker_blocked = "topology claim blockers" in str(exc)

    fail_closed = fail_closed_topology_report()
    fail_closed_ok = (
        fail_closed.status == "not_assessed"
        and fail_closed.topology_fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
        and "topology_validity_not_assessed" in fail_closed.claim_blockers
    )
    passed = placeholder_blocked and blocker_blocked and fail_closed_ok
    return _row(
        check_id="topology_validity_contract_surface",
        category="contract_layer",
        passed=passed,
        observed=(
            f"placeholder_blocked={placeholder_blocked};blocker_blocked={blocker_blocked};"
            f"fail_closed_ok={fail_closed_ok}"
        ),
        required=(
            "TopologyValidityReport blocks claim-safe with placeholder alanine or topology claim blockers "
            "and fail_closed_topology_report emits explicit not-assessed claim blockers"
        ),
    ) | {
        "placeholder_blocked": placeholder_blocked,
        "blocker_blocked": blocker_blocked,
        "fail_closed_ok": fail_closed_ok,
    }


def _check_topology_factory_adapter() -> dict[str, Any]:
    import inspect
    from pathlib import Path

    from betelgeuze_ai_md.contracts import (
        TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
        TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
        build_topology_validity_report,
    )
    import betelgeuze_ai_md.contracts.topology_adapter as topology_adapter_mod

    adapter_source = Path(inspect.getsourcefile(topology_adapter_mod) or "")
    adapter_text = adapter_source.read_text(encoding="utf-8") if adapter_source.is_file() else ""
    no_torch_import = "import torch" not in adapter_text and "from torch" not in adapter_text

    placeholder = build_topology_validity_report(
        {
            "topology_fidelity": TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
            "n_res": 4,
        }
    )
    placeholder_ok = (
        placeholder.status == "not_assessed"
        and placeholder.topology_fidelity == TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE
        and "topology_validity_not_assessed" in placeholder.claim_blockers
        and "placeholder_topology_fidelity" in placeholder.claim_blockers
    )

    class _SequenceMappedTopology:
        n_res = 5
        residue_types_source = TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
        claim_metadata = {"topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED}

        def topology_fidelity(self) -> str:
            return TOPOLOGY_FIDELITY_SEQUENCE_MAPPED

        class _ResidueTypes:
            shape = (5,)

        residue_types = _ResidueTypes()

    sequence_mapped = build_topology_validity_report(_SequenceMappedTopology())
    sequence_mapped_ok = (
        sequence_mapped.status == "pass"
        and sequence_mapped.topology_fidelity == TOPOLOGY_FIDELITY_SEQUENCE_MAPPED
        and sequence_mapped.validity_rows
        and not sequence_mapped.claim_blockers
        and any(row.get("check_id") == "residue_count_coherent" for row in sequence_mapped.validity_rows)
    )

    passed = no_torch_import and placeholder_ok and sequence_mapped_ok
    return _row(
        check_id="topology_factory_adapter_surface",
        category="contract_layer",
        passed=passed,
        observed=(
            f"no_torch_import={no_torch_import};placeholder_ok={placeholder_ok};"
            f"sequence_mapped_ok={sequence_mapped_ok}"
        ),
        required=(
            "topology adapter exports fail-closed placeholder and passing sequence-mapped "
            "TopologyValidityReport surfaces without importing torch at module import time"
        ),
    ) | {
        "no_torch_import": no_torch_import,
        "placeholder_ok": placeholder_ok,
        "sequence_mapped_ok": sequence_mapped_ok,
    }


def _check_backmapping_interaction_adapter_surface() -> dict[str, Any]:
    import inspect
    from pathlib import Path

    import betelgeuze_ai_md.contracts.backmapping_adapter as backmapping_adapter_mod
    import betelgeuze_ai_md.contracts.interaction_adapter as interaction_adapter_mod
    from betelgeuze_ai_md.contracts import build_backmapped_pose, build_interaction_report

    backmapping_source = Path(inspect.getsourcefile(backmapping_adapter_mod) or "")
    interaction_source = Path(inspect.getsourcefile(interaction_adapter_mod) or "")
    backmapping_text = backmapping_source.read_text(encoding="utf-8") if backmapping_source.is_file() else ""
    interaction_text = interaction_source.read_text(encoding="utf-8") if interaction_source.is_file() else ""
    no_torch_import = (
        "import torch" not in backmapping_text
        and "from torch" not in backmapping_text
        and "import torch" not in interaction_text
        and "from torch" not in interaction_text
    )

    ok_pose = build_backmapped_pose(
        {
            "pose_id": "pose_ok_001",
            "structure_path": "runs/pose_ok_001.sdf",
            "structure_sha256": "a" * 64,
            "repair_operations": ["kabsch_alignment"],
            "backmap_status": "ok",
            "site_count": 4,
            "elements": ["O", "N", "S", "P"],
            "roles": ["acceptor", "donor", "donor", "acceptor"],
            "backmap_confidence": 0.92,
        }
    )
    ok_pose_ok = (
        ok_pose.chemical_validity_summary.get("status") == "pass"
        and ok_pose.chemical_validity_summary.get("check_id") == "onsps_4bead_backmap"
        and ok_pose.chemical_validity_summary.get("site_count") == 4
        and 0.0 <= ok_pose.backmap_confidence <= 1.0
        and not ok_pose.chemical_validity_summary.get("claim_blockers")
    )

    no_sites_pose = build_backmapped_pose(
        {
            "pose_id": "pose_empty_001",
            "structure_path": "runs/pose_empty_001.sdf",
            "structure_sha256": "b" * 64,
            "backmap_status": "no_onsps_sites",
            "site_count": 0,
        }
    )
    no_sites_fail_closed = (
        no_sites_pose.chemical_validity_summary.get("status") == "not_assessed"
        and "backmapping_no_onsps_sites" in no_sites_pose.chemical_validity_summary.get(
            "claim_blockers", []
        )
        and no_sites_pose.backmap_confidence == 0.0
    )

    empty_pose = build_backmapped_pose(
        {
            "pose_id": "pose_empty_002",
            "structure_path": "runs/pose_empty_002.sdf",
            "structure_sha256": "c" * 64,
            "backmap_status": "empty_input",
        }
    )
    empty_fail_closed = (
        empty_pose.chemical_validity_summary.get("status") == "not_assessed"
        and "backmapping_empty_input" in empty_pose.chemical_validity_summary.get(
            "claim_blockers", []
        )
        and empty_pose.backmap_confidence == 0.0
    )

    missing_interactions = build_interaction_report()
    missing_ok = "interaction_evidence_missing" in missing_interactions.claim_blockers
    missing_confidence_zero = missing_interactions.interaction_confidence == 0.0

    role_invalid_report = build_interaction_report(
        interactions=[
            {
                "interaction_id": "hbond_001",
                "interaction_type": "hbond",
                "partners": ["SER:OG", "lig1:O1"],
                "distance": 2.9,
                "occupancy": 0.5,
                "confidence": 0.7,
                "role_valid": False,
            }
        ]
    )
    role_invalid_ok = (
        "interaction_role_invalid" in role_invalid_report.claim_blockers
        and role_invalid_report.interactions[0].role_valid is False
    )

    unsupported_report = build_interaction_report(
        interactions=[
            {
                "interaction_id": "weird_001",
                "interaction_type": "weird_chemistry",
                "partners": ["A", "B"],
                "occupancy": 0.4,
                "confidence": 0.6,
            }
        ]
    )
    unsupported_ok = "interaction_type_unsupported" in unsupported_report.claim_blockers

    passed = (
        no_torch_import
        and ok_pose_ok
        and no_sites_fail_closed
        and empty_fail_closed
        and missing_ok
        and missing_confidence_zero
        and role_invalid_ok
        and unsupported_ok
    )
    return _row(
        check_id="backmapping_interaction_adapter_surface",
        category="contract_layer",
        passed=passed,
        observed=(
            f"no_torch_import={no_torch_import};ok_pose_ok={ok_pose_ok};"
            f"no_sites_fail_closed={no_sites_fail_closed};empty_fail_closed={empty_fail_closed};"
            f"missing_ok={missing_ok};role_invalid_ok={role_invalid_ok};"
            f"unsupported_ok={unsupported_ok}"
        ),
        required=(
            "backmapping and interaction adapters emit typed BackmappedPose/InteractionReport with "
            "passing chemical validity for ONSPS-ok pose and explicit fail-closed blockers for "
            "missing/empty/role-invalid/unsupported inputs"
        ),
    ) | {
        "no_torch_import": no_torch_import,
        "ok_pose_ok": ok_pose_ok,
        "no_sites_fail_closed": no_sites_fail_closed,
        "empty_fail_closed": empty_fail_closed,
        "missing_ok": missing_ok,
        "role_invalid_ok": role_invalid_ok,
        "unsupported_ok": unsupported_ok,
    }


def _check_api_evidence_bundle_adapter() -> dict[str, Any]:
    from betelgeuze_ai_md.contracts.api_adapter import build_api_evidence_bundle
    from betelgeuze_ai_md.contracts.output_schema import TopologyValidityReport

    bundle = build_api_evidence_bundle(
        job_id="gate_smoke",
        request={"target_name": "gate_target", "runner_profile_id": "gate_profile"},
        result_manifest={
            "job_id": "gate_smoke",
            "status": "completed",
            "request_sha256": "i" * 64,
            "result_file": "",
            "result_file_sha256": "",
            "claim_scope": "product_ligand_htvs_backmapping",
            "topology_fidelity": "placeholder_alanine",
            "accuracy_claim_grade": "restricted-local-delivery",
            "signature_key_id": "gate",
        },
        result_payload={},
        runner_execution={},
        status_payload={"status": "completed"},
    )
    required_flags = {
        "backmapped_pose_contract_missing",
        "interaction_report_contract_missing",
        "topology_report_contract_missing",
        "delivery_bundle_validation_not_attached",
    }
    observed_flags = set(bundle.failure_flags)
    topology_typed = isinstance(bundle.topology_report, TopologyValidityReport)
    topology_fail_closed = (
        "topology_validity_not_assessed" in bundle.topology_report.claim_blockers
    )
    passed = (
        bundle.verdict.claim_safe is False
        and required_flags.issubset(observed_flags)
        and len(bundle.fingerprint()) == 64
        and topology_typed
        and topology_fail_closed
    )
    return _row(
        check_id="api_evidence_bundle_adapter_fail_closed",
        category="api_evidence_bundle",
        passed=passed,
        observed=(
            f"claim_safe={bundle.verdict.claim_safe};flags={len(observed_flags)};"
            f"topology_typed={topology_typed};topology_fail_closed={topology_fail_closed};"
            f"fingerprint_len={len(bundle.fingerprint())}"
        ),
        required=(
            "API adapter emits deterministic review-only EvidenceBundle with missing-evidence flags "
            "and a typed TopologyValidityReport carrying explicit not-assessed claim blockers"
        ),
    ) | {
        "failure_flags": sorted(observed_flags),
        "topology_typed": topology_typed,
        "topology_fail_closed": topology_fail_closed,
    }


def _check_api_job_store_evidence_bundle_persistence(root: Path) -> dict[str, Any]:
    job_store = _resolve("api/job_store.py", root=root)
    text = job_store.read_text(encoding="utf-8") if job_store.is_file() else ""
    required_fragments = [
        "evidence_bundle_path TEXT NOT NULL DEFAULT ''",
        "evidence_bundle_sha256 TEXT NOT NULL DEFAULT ''",
        'ADD COLUMN evidence_bundle_path TEXT NOT NULL DEFAULT',
        'ADD COLUMN evidence_bundle_sha256 TEXT NOT NULL DEFAULT',
        "evidence_bundle_path: str | None = None",
        "evidence_bundle_sha256: str | None = None",
        "evidence_bundle_path=''",
        "evidence_bundle_sha256=''",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in text]
    return _row(
        check_id="api_job_store_evidence_bundle_persistence",
        category="api_evidence_bundle",
        passed=not missing,
        observed=f"required_fragments={len(required_fragments)};missing={len(missing)}",
        required=(
            "SQLite job store persists evidence_bundle_path and evidence_bundle_sha256 with "
            "migration and clears pointers on job recreation"
        ),
        artifact_paths=["api/job_store.py"],
    ) | {"missing_fragments": missing, "missing_fragment_count": len(missing)}


def _check_api_main_evidence_bundle_surface(root: Path) -> dict[str, Any]:
    main_py = _resolve("api/main.py", root=root)
    models_py = _resolve("api/models.py", root=root)
    main_text = main_py.read_text(encoding="utf-8") if main_py.is_file() else ""
    models_text = models_py.read_text(encoding="utf-8") if models_py.is_file() else ""
    required_fragments = [
        "result_manifest=_artifact_path",
        "evidence_bundle=_artifact_path",
        "evidence_bundle_sha256=_artifact_path",
        "Completed job missing result manifest provenance",
        "Completed job missing evidence bundle provenance",
        "Completed job missing evidence bundle fingerprint",
        "result_manifest: Optional[str] = None",
        "evidence_bundle: Optional[str] = None",
        "evidence_bundle_sha256: Optional[str] = None",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in (main_text + models_text)]
    return _row(
        check_id="api_main_evidence_bundle_surface",
        category="api_evidence_bundle",
        passed=not missing,
        observed=f"required_fragments={len(required_fragments)};missing={len(missing)}",
        required=(
            "API status/results surfaces expose evidence bundle provenance and fail closed when "
            "completed jobs lack manifest or evidence bundle pointers"
        ),
        artifact_paths=["api/main.py", "api/models.py"],
    ) | {"missing_fragments": missing, "missing_fragment_count": len(missing)}


def _check_api_worker_attachment(root: Path) -> dict[str, Any]:
    worker = _resolve("api/worker.py", root=root)
    text = worker.read_text(encoding="utf-8") if worker.is_file() else ""
    required_fragments = [
        "write_api_evidence_bundle",
        "job_evidence_bundle_path",
        "write_job_evidence_bundle",
        '"evidence_bundle"',
        '"evidence_bundle_sha256"',
        "evidence_bundle_path=bundle_path",
        "evidence_bundle_sha256=bundle_hash",
        "read_json_object_file",
    ]
    missing = [fragment for fragment in required_fragments if fragment not in text]
    return _row(
        check_id="api_worker_evidence_bundle_attachment",
        category="api_evidence_bundle",
        passed=not missing,
        observed=f"required_fragments={len(required_fragments)};missing={len(missing)}",
        required="API worker completed-job flow writes evidence_bundle path and fingerprint without assuming result file JSON",
        artifact_paths=["api/worker.py"],
    ) | {"missing_fragments": missing, "missing_fragment_count": len(missing)}


def _check_api_validated_runner_native_evidence_bundle_support(root: Path) -> dict[str, Any]:
    validated_runner = _resolve("api/validated_runner.py", root=root)
    worker = _resolve("api/worker.py", root=root)
    profiles_validator = _resolve("tools/product/validate_api_runner_profiles.py", root=root)
    runner_text = validated_runner.read_text(encoding="utf-8") if validated_runner.is_file() else ""
    worker_text = worker.read_text(encoding="utf-8") if worker.is_file() else ""
    validator_text = profiles_validator.read_text(encoding="utf-8") if profiles_validator.is_file() else ""
    required_fragments = [
        ("validated_runner.evidence_bundle_template", '"evidence_bundle_template"', runner_text),
        ("validated_runner.context.evidence_bundle", '"evidence_bundle"', runner_text),
        ("validated_runner.EvidenceBundle_import", "from betelgeuze_ai_md.contracts import EvidenceBundle", runner_text),
        ("validated_runner.ContractValidationError_import", "ContractValidationError", runner_text),
        ("validated_runner.native_evidence_bundle_record", "native_evidence_bundle", runner_text),
        ("validated_runner.evidence_bundle_source", "evidence_bundle_source", runner_text),
        ("worker.adopt_validated_runner_native_evidence_bundle", "adopt_validated_runner_native_evidence_bundle", worker_text),
        ("worker.bundle.fingerprint()", "bundle.fingerprint()", worker_text),
        ("worker.final_evidence_bundle_path", "final_path = Path(job_evidence_bundle_path(job_id))", worker_text),
        ("validator.evidence_bundle_template_declared", "evidence_bundle_template_declared", validator_text),
    ]
    missing = [name for name, fragment, text in required_fragments if fragment not in text]
    return _row(
        check_id="api_validated_runner_native_evidence_bundle_support",
        category="api_evidence_bundle",
        passed=not missing,
        observed=f"required_fragments={len(required_fragments)};missing={len(missing)}",
        required=(
            "validated runner profile supports evidence_bundle_template, runner command context exposes "
            "{evidence_bundle}, native bundles are validated as EvidenceBundle with fingerprint, the worker "
            "adopts validated native bundles as final evidence_bundle.json, and the profile validator "
            "reports native bundle template presence"
        ),
        artifact_paths=[
            "api/validated_runner.py",
            "api/worker.py",
            "tools/product/validate_api_runner_profiles.py",
        ],
    ) | {"missing_fragments": missing, "missing_fragment_count": len(missing)}


def _check_numpy_reference_oracle() -> dict[str, Any]:
    from betelgeuze_ai_md.coarse_md.numpy_ref import (
        BeadKind,
        CoarseForceField,
        CoarseState,
        NeighborListBuilder,
        ScreenedElectrostaticTerm,
        finite_difference_force,
    )

    state = CoarseState(
        x=np.array([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0]], dtype=np.float32),
        v=np.zeros((2, 3), dtype=np.float32),
        mass=np.ones(2, dtype=np.float32) * 12.0,
        charge=np.array([1.0, -1.0], dtype=np.float32),
        radius=np.ones(2, dtype=np.float32) * 1.6,
        epsilon=np.zeros(2, dtype=np.float32),
        bead_type=np.array([BeadKind.LIGAND_CHARGED, BeadKind.LIGAND_CHARGED], dtype=np.int32),
        feature=np.zeros(2, dtype=np.int32),
        mol_id=np.array([0, 1], dtype=np.int32),
        fixed=np.zeros(2, dtype=bool),
    )
    neighbor_builder = NeighborListBuilder(cutoff=6.0, skin=0.0)
    forcefield = CoarseForceField(
        [ScreenedElectrostaticTerm(epsilon_r=20.0, kappa=0.15, r_switch=5.0, r_cut=6.0)],
        force_clip=1_000_000.0,
    )

    def energy_fn(x: np.ndarray) -> float:
        shifted = state.with_positions(x)
        return forcefield.compute(shifted, neighbor_builder.build(shifted.x)).energy

    result = forcefield.compute(state, neighbor_builder.build(state.x))
    fd_force = finite_difference_force(energy_fn, state.x, h=1e-3)
    force_matches = bool(np.allclose(result.forces, fd_force, rtol=3e-3, atol=3e-3))
    passed = bool(np.isfinite(result.energy) and np.isfinite(result.forces).all() and force_matches)
    return _row(
        check_id="numpy_reference_oracle_smoke",
        category="numpy_reference_oracle",
        passed=passed,
        observed=f"finite_energy={np.isfinite(result.energy)};force_matches_finite_difference={force_matches}",
        required="NumPy reference oracle produces finite energy/forces and matches finite-difference force",
    )


def build_ai_md_contract_source_of_truth_gate(
    *,
    root: str | Path = ROOT,
    required_source_files: list[str] | None = None,
) -> dict[str, Any]:
    root_path = Path(root)
    source_files = list(required_source_files or REQUIRED_SOURCE_FILES)
    checks = [
        lambda: _check_required_source_files(root_path, source_files),
        lambda: _check_pyproject_package_discovery(root_path),
        _check_contract_symbols_exported,
        _check_topology_validity_contract_surface,
        _check_topology_factory_adapter,
        _check_backmapping_interaction_adapter_surface,
        _check_claim_widening_guard,
        _check_api_evidence_bundle_adapter,
        lambda: _check_api_job_store_evidence_bundle_persistence(root_path),
        lambda: _check_api_main_evidence_bundle_surface(root_path),
        lambda: _check_api_worker_attachment(root_path),
        lambda: _check_api_validated_runner_native_evidence_bundle_support(root_path),
        _check_numpy_reference_oracle,
    ]
    rows = [_safe_check(check) for check in checks]
    blockers = [row for row in rows if row["release_blocker"]]
    rows_by_id = {str(row["check_id"]): row for row in rows}
    category_ready = {
        category: all(row["status"] == "pass" for row in rows if row["category"] == category)
        for category in sorted({row["category"] for row in rows})
    }
    missing_source_file_count = sum(int(row.get("missing_source_file_count", 0)) for row in rows)
    ready = not blockers
    summary = {
        "packet_type": "ai_md_contract_source_of_truth_gate",
        "status": "ai_md_contract_source_of_truth_gate_ready" if ready else "blocked_ai_md_contract_source_of_truth_gate",
        "ai_md_contract_source_of_truth_gate_ready": ready,
        "ai_md_contract_layer_ready": bool(category_ready.get("contract_layer")),
        "api_evidence_bundle_attachment_ready": bool(category_ready.get("api_evidence_bundle")),
        "api_runtime_evidence_bundle_surface_ready": all(
            rows_by_id.get(check_id, {}).get("status") == "pass"
            for check_id in (
                "api_job_store_evidence_bundle_persistence",
                "api_main_evidence_bundle_surface",
                "api_worker_evidence_bundle_attachment",
                "api_validated_runner_native_evidence_bundle_support",
            )
        ),
        "numpy_reference_oracle_ready": bool(category_ready.get("numpy_reference_oracle")),
        "claim_widening_guard_ready": bool(category_ready.get("claim_boundary")),
        "contract_source_files_ready": bool(category_ready.get("contract_source_files")),
        "topology_validity_contract_ready": rows_by_id.get("topology_validity_contract_surface", {}).get("status")
        == "pass",
        "topology_factory_adapter_ready": rows_by_id.get("topology_factory_adapter_surface", {}).get("status")
        == "pass",
        "backmapping_interaction_adapter_ready": rows_by_id.get(
            "backmapping_interaction_adapter_surface", {}
        ).get("status")
        == "pass",
        "check_count": len(rows),
        "pass_count": len(rows) - len(blockers),
        "blocker_count": len(blockers),
        "missing_source_file_count": missing_source_file_count,
        "blocked_check_ids": [row["check_id"] for row in blockers],
        "required_source_file_count": len(source_files),
        "execution_enabled": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "full_commercial_claim_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Wire this artifact into product release source-of-truth freshness and semantic-status rows."
            if ready
            else "Restore missing contract/API/reference files or fail-closed claim guards, then rerun this gate."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _resolve_out(path_like: str | Path, *, root: Path) -> Path:
    return _resolve(path_like, root=root)


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve_out(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve_out(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# AI-MD Contract Source Of Truth Gate",
        "",
        f"- status: `{summary['status']}`",
        f"- ready: `{summary['ai_md_contract_source_of_truth_gate_ready']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- contract_source_files_ready: `{summary['contract_source_files_ready']}`",
        f"- ai_md_contract_layer_ready: `{summary['ai_md_contract_layer_ready']}`",
        f"- api_evidence_bundle_attachment_ready: `{summary['api_evidence_bundle_attachment_ready']}`",
        f"- api_runtime_evidence_bundle_surface_ready: `{summary['api_runtime_evidence_bundle_surface_ready']}`",
        f"- numpy_reference_oracle_ready: `{summary['numpy_reference_oracle_ready']}`",
        f"- claim_widening_guard_ready: `{summary['claim_widening_guard_ready']}`",
        "",
        "## Checks",
        "",
        "| check | category | status | observed | required |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['category']}` | `{row['status']}` | "
            f"`{row['observed']}` | `{row['required']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], "", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AI-MD contract source-of-truth gate.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_ai_md_contract_source_of_truth_gate(root=root)
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve_out(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
