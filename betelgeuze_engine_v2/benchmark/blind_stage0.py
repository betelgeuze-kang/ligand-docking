"""Fail-closed Stage 0 admission for the public redocking blind holdout."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import hashlib
from importlib import metadata
import importlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any, Mapping

from betelgeuze_engine_v2.docking.torsion_contact_refinement import (
    INTERACTION_AWARE_TORSION_CONTACT_CONFIG_V7_SCHEMA_ID,
    INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_ID,
    INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_VERSION,
    InteractionAwareTorsionContactConfigV7,
)

from .public_redocking_benchmark import (
    PUBLIC_REDOCKING_ENGINE_V2_ALGORITHM_PROFILE_ID,
    PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT,
    PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID,
    PUBLIC_REDOCKING_ENGINE_V2_REFINER_CONFIG_SHA256,
    PUBLIC_REDOCKING_RUNNER_ID,
)


STAGE0_SCHEMA_VERSION = 1
STAGE0_PROTOCOL_ID = "engine_v2_fresh_redocking_128_stage0_v1"
STAGE0_DIAGNOSTIC_CONTRACT_ID = (
    "betelgeuze-engine-v2-public-redocking-diagnostics/0.2.0rc5"
)
STAGE0_PRIMARY_CASE_COUNT = 128
STAGE0_DEVELOPMENT_CASE_COUNT = 300
STAGE0_TOTAL_CASE_COUNT = 428
STAGE0_ENGINE_ROW_COUNT = 384
STAGE0_CANDIDATE_DIAGNOSTIC_SLOT_COUNT = 8_192
STAGE0_DIAGNOSTIC_REVIEW_HEAD_SHA = "3935a1fa8f0a8f82c78f50c416db46a87abd319e"
STAGE0_ENGINE_V2_ALGORITHM_PROFILE_ID = PUBLIC_REDOCKING_ENGINE_V2_ALGORITHM_PROFILE_ID

_REQUIRED_THRESHOLDS = {
    "preparation_input_unsupported_rate": "max",
    "candidate_generation_coverage": "min",
    "proposal_oracle_2a_recovery": "min",
    "top1_selection_failure_given_oracle": "max",
    "top5_selection_failure_given_oracle": "max",
    "invalid_top1_pose_rate": "max",
    "case_level_failure_rate": "max",
}
_REQUIRED_THRESHOLD_DENOMINATORS = {
    "preparation_input_unsupported_rate": "all_cases",
    "candidate_generation_coverage": "preparation_success_cases",
    "proposal_oracle_2a_recovery": "preparation_success_cases",
    "top1_selection_failure_given_oracle": "proposal_oracle_success_cases",
    "top5_selection_failure_given_oracle": "proposal_oracle_success_cases",
    "invalid_top1_pose_rate": "preparation_success_cases",
    "case_level_failure_rate": "all_cases",
}
_REQUIRED_BRANCHES = {
    "preparation_coverage_low": "preparation_track",
    "proposal_oracle_low": "proposal_track",
    "oracle_high_top5_low": "ranking_track",
    "top5_high_top1_low": "scorer_calibration_track",
    "rmsd_good_validity_low": "refinement_validity_track",
    "small_ligand_only_success": "capacity_bias_track",
    "rotor_5plus_drop": "flexible_ligand_search_track",
    "ring_subgroup_drop": "ring_conformer_track",
    "hbond_features_unrealized": "multi_anchor_track",
}
_ALLOWED_PROVENANCE_BASES = {
    "public_development_corpus",
}
_THRESHOLD_EVIDENCE_SCHEMA_ID = "betelgeuze.engine_v2_stage0_threshold_evidence/1.0.0"
_REQUIRED_SUITE_CATEGORIES = {
    "actual_regression",
    "fixture_dependent",
    "host_capability_missing",
    "local_evidence_required",
    "legacy_deterministic",
    "product_fixture_dependent",
}
STAGE0_REQUIRED_SOURCE_FREEZE_PATHS = frozenset(
    {
        "tools/run_engine_v2_public_redocking_300.py",
        "tools/freeze_engine_v2_fresh_holdout.py",
        "tools/derive_engine_v2_stage0_threshold_evidence.py",
        "tools/analyze_engine_v2_score_terms.py",
        "tools/verify_engine_v2_public_redocking_stage0.py",
        "tools/classify_engine_v2_stage0_full_suite.py",
        "tools/reconcile_engine_v2_stage0_full_suites.py",
        "tools/audit_engine_v2_ci_authority.py",
        "betelgeuze_engine_v2/benchmark/blind_stage0.py",
        "betelgeuze_engine_v2/benchmark/fresh_redocking_holdout.py",
        "betelgeuze_engine_v2/benchmark/public_redocking_benchmark.py",
        "config/engine_v2_public_redocking_contamination_registry.json",
        "config/engine_v2_fresh_redocking_holdout_manifest.json",
        "betelgeuze_engine_v2/docking/__init__.py",
        "betelgeuze_engine_v2/docking/authority.py",
        "betelgeuze_engine_v2/docking/conformers.py",
        "betelgeuze_engine_v2/docking/contact_validity.py",
        "betelgeuze_engine_v2/docking/energy_refinement.py",
        "betelgeuze_engine_v2/docking/guided_placement.py",
        "betelgeuze_engine_v2/docking/interaction_refinement.py",
        "betelgeuze_engine_v2/docking/proposals.py",
        "betelgeuze_engine_v2/docking/scorer_v1.py",
        "betelgeuze_engine_v2/docking/scoring.py",
        "betelgeuze_engine_v2/docking/search.py",
        "betelgeuze_engine_v2/docking/torsion_contact_refinement.py",
        "packaging/engine-v2/pyproject.toml",
        "tools/build_engine_v2_native_wheel.py",
        "tools/build_engine_v2_sbom.py",
        "rust_engine_v2/Cargo.toml",
        "rust_engine_v2/Cargo.lock",
        "rust_engine_v2/build.rs",
        "rust_engine_v2/pyproject.toml",
        "rust_engine_v2/src/lib.rs",
    }
)
_REQUIRED_SOURCE_FREEZE_PATHS = STAGE0_REQUIRED_SOURCE_FREEZE_PATHS
_RUNTIME_ENVIRONMENT_KEYS = (
    "CUDA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "ROCR_VISIBLE_DEVICES",
    "VECLIB_MAXIMUM_THREADS",
)
_AUTHORITATIVE_CI_WORKFLOWS = (
    ".github/workflows/ci-engine-v2-main.yml",
    ".github/workflows/ci-engine-v2-release-candidate.yml",
    ".github/workflows/ci-engine-v2-cpu-reference-validation-protocol.yml",
)


class Stage0AdmissionError(RuntimeError):
    """The blind holdout is not admitted by a complete frozen contract."""

    def __init__(self, blockers: tuple[str, ...]) -> None:
        self.blockers = blockers
        super().__init__("Stage 0 admission blocked: " + "; ".join(blockers))


@dataclass(frozen=True)
class VerifiedStage0Admission:
    """A locally verified, result-independent Stage 0 freeze receipt."""

    policy_sha256: str
    source_freeze_sha256: str
    reviewer_id: str
    operator_id: str
    governance_mode: str
    independent_review_complete: bool


def current_stage0_native_backend() -> dict[str, Any]:
    """Return the installed native scorer identity used by a blind run."""

    module = importlib.import_module("betelgeuze_engine_v2_native")
    extension_module = getattr(module, "betelgeuze_engine_v2_native", module)
    module_path = Path(str(extension_module.__file__)).resolve()
    if not module_path.is_file() or module_path.suffix != ".so":
        raise Stage0AdmissionError(("native_backend_extension_invalid",))
    build_info = module.build_info()
    if not isinstance(build_info, dict):
        raise Stage0AdmissionError(("native_backend_build_info_invalid",))
    try:
        distribution_version = metadata.version("betelgeuze-engine-v2-native")
    except metadata.PackageNotFoundError as exc:
        raise Stage0AdmissionError(("native_backend_distribution_missing",)) from exc
    return {
        "backend": "rust_cpu_required",
        "distribution_version": distribution_version,
        "extension_path": str(module_path),
        "extension_sha256": _sha256_path(module_path),
        "cargo_lock_sha256": _text(build_info.get("cargo_lock_sha256")),
        "rustc_version": _text(build_info.get("rustc_version")),
        "target_triple": _text(build_info.get("target_triple")),
        "build_flags": _text(build_info.get("build_flags")),
        "thread_count": 1,
    }


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_stage0_policy_sha256(payload: Mapping[str, Any]) -> str:
    """Return the canonical hash, excluding the self-hash field."""

    unhashed = dict(payload)
    unhashed.pop("policy_sha256", None)
    return hashlib.sha256(_canonical_bytes(unhashed)).hexdigest()


def compute_stage0_review_subject_sha256(payload: Mapping[str, Any]) -> str:
    """Hash the policy content reviewed before attaching its attestation."""

    subject = json.loads(json.dumps(payload))
    subject.pop("policy_sha256", None)
    governance = subject.get("governance")
    if isinstance(governance, dict):
        governance.pop("independent_attestation_path", None)
        governance.pop("independent_attestation_sha256", None)
        governance.pop("solo_attestation_path", None)
        governance.pop("solo_attestation_sha256", None)
    return hashlib.sha256(_canonical_bytes(subject)).hexdigest()


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_sha256(value: object) -> bool:
    text = _text(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def stage0_engine_v2_algorithm_profile() -> dict[str, object]:
    """Return the one exact V7 algorithm profile admitted by Stage 0."""

    config = InteractionAwareTorsionContactConfigV7()
    if config.fingerprint_sha256 != PUBLIC_REDOCKING_ENGINE_V2_REFINER_CONFIG_SHA256:
        raise Stage0AdmissionError(("stage0_v7_config_fingerprint_drift",))
    return {
        "schema_id": ("betelgeuze.engine_v2_public_redocking_algorithm_profile/1.0.0"),
        "profile_id": STAGE0_ENGINE_V2_ALGORITHM_PROFILE_ID,
        "runner_id": PUBLIC_REDOCKING_RUNNER_ID,
        "candidate_schema_id": PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID,
        "candidate_budget": PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_COUNT,
        "active_refiner": {
            "refiner_id": INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_ID,
            "refiner_version": INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_VERSION,
            "config_schema_id": INTERACTION_AWARE_TORSION_CONTACT_CONFIG_V7_SCHEMA_ID,
            "config_sha256": PUBLIC_REDOCKING_ENGINE_V2_REFINER_CONFIG_SHA256,
            "config": config.to_dict(),
        },
        "selection_window": {
            "metric": "final_receptor_quartic_overlap_penalty",
            "interval": "[2.0,4.0)",
            "minimum_binary64_hex": (
                config.minimum_selected_final_receptor_penalty.hex()
            ),
            "maximum_binary64_hex": (
                config.maximum_selected_final_receptor_penalty.hex()
            ),
            "minimum_inclusive": True,
            "maximum_exclusive": True,
            "result_independent": True,
        },
    }


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _read_json_object(path: Path | None) -> Mapping[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _valid_utc_timestamp(value: object) -> bool:
    text = _text(value)
    if not text.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() is not None


def _utc_datetime(value: object) -> datetime | None:
    if not _valid_utc_timestamp(value):
        return None
    return datetime.fromisoformat(_text(value)[:-1] + "+00:00")


def _distribution_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "missing"


def _cpu_model_sha256() -> str:
    model_rows: list[str] = []
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        try:
            for line in cpuinfo.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition(":")
                if separator and key.strip().lower() in {"model name", "hardware"}:
                    model_rows.append(value.strip())
        except (OSError, UnicodeError):
            model_rows = []
    if not model_rows:
        model_rows = [platform.processor() or "unavailable"]
    return hashlib.sha256(_canonical_bytes(sorted(set(model_rows)))).hexdigest()


def current_stage0_host_environment() -> dict[str, Any]:
    """Return a SHA-only host identity suitable for pre-run freezing."""

    executable = Path(sys.executable).resolve()
    affinity = (
        sorted(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else list(range(os.cpu_count() or 0))
    )
    runtime_hashes = {
        key: (
            hashlib.sha256(os.environ[key].encode("utf-8")).hexdigest()
            if key in os.environ
            else "absent"
        )
        for key in _RUNTIME_ENVIRONMENT_KEYS
    }
    return {
        "system": platform.system(),
        "kernel_release": platform.release(),
        "machine": platform.machine(),
        "python_executable_sha256": (
            _sha256_path(executable) if executable.is_file() else "missing"
        ),
        "logical_cpu_count": os.cpu_count(),
        "cpu_affinity": affinity,
        "cpu_model_sha256": _cpu_model_sha256(),
        "runtime_variable_sha256s": runtime_hashes,
    }


def _resolve_repo_file(repo_root: Path, relative_path: object) -> Path | None:
    text = _text(relative_path)
    if not text:
        return None
    candidate = (repo_root / text).resolve()
    try:
        candidate.relative_to(repo_root.resolve())
    except ValueError:
        return None
    return candidate


def _git(repo_root: Path, *arguments: str) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            ("git", "-C", str(repo_root), *arguments),
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return completed.returncode, completed.stdout.strip()


def _validate_bound_artifact(
    row: Mapping[str, Any],
    *,
    repo_root: Path,
    path_field: str,
    sha_field: str,
    blocker_prefix: str,
    blockers: list[str],
) -> None:
    path = _resolve_repo_file(repo_root, row.get(path_field))
    if path is None or not path.is_file():
        blockers.append(f"{blocker_prefix}_artifact_missing")
        return
    if row.get(sha_field) != _sha256_path(path):
        blockers.append(f"{blocker_prefix}_artifact_hash_mismatch")


def _validate_threshold_evidence(
    provenance: Mapping[str, Any],
    *,
    metric: str,
    operator: str,
    value: object,
    repo_root: Path,
    blockers: list[str],
) -> None:
    evidence_path = _resolve_repo_file(repo_root, provenance.get("evidence_path"))
    evidence = _read_json_object(evidence_path)
    if evidence.get("schema_id") != _THRESHOLD_EVIDENCE_SCHEMA_ID:
        blockers.append(f"threshold_evidence_schema_invalid:{metric}")
    if evidence.get("contains_engineering_smoke") is not False:
        blockers.append(f"threshold_evidence_contains_smoke:{metric}")
    if evidence.get("contains_primary_holdout") is not False:
        blockers.append(f"threshold_evidence_contains_holdout:{metric}")
    if evidence.get("contains_fresh_internal_blind_holdout") is not False:
        blockers.append(f"threshold_evidence_contains_fresh_holdout:{metric}")
    case_count = evidence.get("case_count")
    if type(case_count) is not int or case_count < 1:
        blockers.append(f"threshold_evidence_case_count_invalid:{metric}")
    if not _is_sha256(evidence.get("case_ids_sha256")):
        blockers.append(f"threshold_evidence_case_identity_missing:{metric}")
    if evidence.get("diagnostic_contract_id") != STAGE0_DIAGNOSTIC_CONTRACT_ID:
        blockers.append(f"threshold_evidence_contract_mismatch:{metric}")
    if not _text(evidence.get("sample_size_justification")):
        blockers.append(f"threshold_evidence_sample_size_unjustified:{metric}")
    metrics = _mapping(evidence.get("metrics"))
    metric_row = _mapping(metrics.get(metric))
    if metric_row.get("operator") != operator:
        blockers.append(f"threshold_evidence_operator_mismatch:{metric}")
    if metric_row.get("proposed_threshold") != value:
        blockers.append(f"threshold_evidence_value_mismatch:{metric}")
    observed_estimate = metric_row.get("observed_estimate")
    if type(observed_estimate) not in (int, float):
        blockers.append(f"threshold_evidence_estimate_missing:{metric}")
    elif type(value) in (int, float):
        observed = float(observed_estimate)
        threshold = float(value)
        if (operator == "min" and observed + 1.0e-15 < threshold) or (
            operator == "max" and observed - 1.0e-15 > threshold
        ):
            blockers.append(f"threshold_development_gate_failed:{metric}")
    if not _text(metric_row.get("derivation_rule")):
        blockers.append(f"threshold_evidence_derivation_missing:{metric}")
    denominator_policy = _mapping(evidence.get("metric_denominator_policy"))
    if denominator_policy.get(metric) != _REQUIRED_THRESHOLD_DENOMINATORS[metric]:
        blockers.append(f"threshold_evidence_denominator_mismatch:{metric}")


def _validate_thresholds(
    payload: Mapping[str, Any], repo_root: Path, blockers: list[str]
) -> None:
    thresholds = _mapping(payload.get("acceptance_thresholds"))
    if set(thresholds) != set(_REQUIRED_THRESHOLDS):
        blockers.append("acceptance_threshold_axes_incomplete")
        return
    for metric, operator in _REQUIRED_THRESHOLDS.items():
        row = _mapping(thresholds.get(metric))
        value = row.get("value")
        if row.get("operator") != operator:
            blockers.append(f"threshold_operator_invalid:{metric}")
        if type(value) not in (int, float) or not 0.0 <= float(value) <= 1.0:
            blockers.append(f"threshold_value_not_frozen:{metric}")
        if row.get("analysis_scope") != "fresh_internal_blind_holdout":
            blockers.append(f"threshold_scope_invalid:{metric}")
        if row.get("denominator") != _REQUIRED_THRESHOLD_DENOMINATORS[metric]:
            blockers.append(f"threshold_denominator_invalid:{metric}")
        provenance = _mapping(row.get("provenance"))
        if provenance.get("basis") not in _ALLOWED_PROVENANCE_BASES:
            blockers.append(f"threshold_provenance_basis_invalid:{metric}")
        if not _is_sha256(provenance.get("evidence_sha256")):
            blockers.append(f"threshold_provenance_hash_missing:{metric}")
        _validate_bound_artifact(
            provenance,
            repo_root=repo_root,
            path_field="evidence_path",
            sha_field="evidence_sha256",
            blocker_prefix=f"threshold_provenance:{metric}",
            blockers=blockers,
        )
        _validate_threshold_evidence(
            provenance,
            metric=metric,
            operator=operator,
            value=value,
            repo_root=repo_root,
            blockers=blockers,
        )
        excluded = set(provenance.get("excluded_sources", ()))
        if "fresh_internal_blind_holdout" not in excluded:
            blockers.append(f"threshold_provenance_leak_boundary_missing:{metric}")


def _validate_baselines(
    payload: Mapping[str, Any], repo_root: Path, blockers: list[str]
) -> None:
    comparison = _mapping(payload.get("baseline_comparison"))
    if comparison.get("engines") != ["vina", "gnina"]:
        blockers.append("baseline_engines_not_frozen")
    if comparison.get("paired_case_analysis") is not True:
        blockers.append("baseline_not_paired")
    if comparison.get("confidence_interval") != "percentile_bootstrap_95pct":
        blockers.append("baseline_ci_rule_not_frozen")
    if comparison.get("decision_rule") != "lower_ci_ge_noninferiority_margin":
        blockers.append("baseline_decision_rule_not_frozen")
    margins = _mapping(comparison.get("noninferiority_margins"))
    required = {"top1_2a_recovery_delta", "top5_2a_recovery_delta"}
    if set(margins) != required or any(
        type(margins.get(metric)) not in (int, float)
        or not -1.0 <= float(margins[metric]) <= 0.0
        for metric in required
    ):
        blockers.append("baseline_noninferiority_margins_not_frozen")
    if comparison.get("runtime_role") != "descriptive_only":
        blockers.append("runtime_role_must_be_descriptive_only")
    if comparison.get("runtime_is_promotion_gate") is not False:
        blockers.append("runtime_must_not_be_promotion_gate")
    provenance = _mapping(comparison.get("provenance"))
    if provenance.get("basis") != "vina_gnina_development_baseline":
        blockers.append("baseline_provenance_basis_invalid")
    excluded = set(provenance.get("excluded_sources", ()))
    if "fresh_internal_blind_holdout" not in excluded:
        blockers.append("baseline_provenance_leak_boundary_missing")
    _validate_bound_artifact(
        provenance,
        repo_root=repo_root,
        path_field="evidence_path",
        sha_field="evidence_sha256",
        blocker_prefix="baseline_provenance",
        blockers=blockers,
    )
    evidence_path = _resolve_repo_file(repo_root, provenance.get("evidence_path"))
    evidence = _read_json_object(evidence_path)
    if evidence.get("schema_id") != _THRESHOLD_EVIDENCE_SCHEMA_ID:
        blockers.append("baseline_evidence_schema_invalid")
    if evidence.get("contains_engineering_smoke") is not False:
        blockers.append("baseline_evidence_contains_smoke")
    if evidence.get("contains_primary_holdout") is not False:
        blockers.append("baseline_evidence_contains_holdout")
    if evidence.get("contains_fresh_internal_blind_holdout") is not False:
        blockers.append("baseline_evidence_contains_fresh_holdout")
    if _mapping(evidence.get("baseline_noninferiority_margins")) != margins:
        blockers.append("baseline_evidence_margin_mismatch")
    if evidence.get("paired_baseline_engines") != ["vina", "gnina"]:
        blockers.append("baseline_evidence_engines_mismatch")


def _validate_branching(payload: Mapping[str, Any], blockers: list[str]) -> None:
    branching = _mapping(payload.get("diagnostic_branching"))
    if branching != _REQUIRED_BRANCHES:
        blockers.append("diagnostic_branching_rules_not_frozen")
    if payload.get("holdout_reuse_policy") != "never_use_fresh_128_for_tuning":
        blockers.append("holdout_reuse_policy_not_frozen")


def _validate_contamination_registry(repo_root: Path, blockers: list[str]) -> None:
    from .fresh_redocking_holdout import load_fresh_redocking_holdout_manifest
    from .public_redocking_benchmark import (
        require_public_redocking_contamination_registry,
    )

    registry = _read_json_object(
        repo_root / "config/engine_v2_public_redocking_contamination_registry.json"
    )
    try:
        require_public_redocking_contamination_registry(registry)
    except (TypeError, ValueError) as exc:
        blockers.append(f"contamination_registry_invalid:{type(exc).__name__}")
    try:
        load_fresh_redocking_holdout_manifest(
            repo_root / "config/engine_v2_fresh_redocking_holdout_manifest.json"
        )
    except (OSError, TypeError, ValueError) as exc:
        blockers.append(f"fresh_holdout_manifest_invalid:{type(exc).__name__}")


def _validate_source_freeze(
    payload: Mapping[str, Any], repo_root: Path, blockers: list[str]
) -> str:
    source_freeze = _mapping(payload.get("source_freeze"))
    algorithm_profile = _mapping(source_freeze.get("algorithm_profile"))
    expected_algorithm_profile = stage0_engine_v2_algorithm_profile()
    if algorithm_profile.get("profile_id") != STAGE0_ENGINE_V2_ALGORITHM_PROFILE_ID:
        blockers.append("source_algorithm_profile_id_not_v7")
    if algorithm_profile.get("runner_id") != PUBLIC_REDOCKING_RUNNER_ID:
        blockers.append("source_runner_id_not_2_13_0")
    if (
        algorithm_profile.get("candidate_schema_id")
        != PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID
    ):
        blockers.append("source_candidate_schema_not_1_6_0")
    if algorithm_profile != expected_algorithm_profile:
        blockers.append("source_algorithm_profile_mismatch")
    if source_freeze.get("candidate_budget") != 64:
        blockers.append("candidate_budget_not_frozen")
    if source_freeze.get("retained_pose_count") != 5:
        blockers.append("retained_pose_count_not_frozen")
    if source_freeze.get("scorer_id") != "chemistry_pose_scorer_v1":
        blockers.append("scorer_id_not_frozen")
    if source_freeze.get("scorer_backend") != "rust_cpu_required":
        blockers.append("scorer_backend_not_frozen")
    if source_freeze.get("native_thread_count") != 1:
        blockers.append("native_thread_count_not_frozen")
    if not _text(source_freeze.get("charge_policy_id")):
        blockers.append("charge_policy_not_frozen")
    if not _text(source_freeze.get("pocket_policy_id")):
        blockers.append("pocket_policy_not_frozen")
    if source_freeze.get("diagnostic_contract_pr_number") != 211:
        blockers.append("diagnostic_contract_pr_not_bound")
    if (
        source_freeze.get("diagnostic_contract_review_head_sha")
        != STAGE0_DIAGNOSTIC_REVIEW_HEAD_SHA
    ):
        blockers.append("diagnostic_contract_review_head_mismatch")
    head_status, actual_head = _git(repo_root, "rev-parse", "HEAD")
    main_status, actual_origin_main = _git(
        repo_root, "rev-parse", "refs/remotes/origin/main"
    )
    if head_status != 0 or not _text(actual_head):
        blockers.append("source_git_head_unavailable")
    if main_status != 0 or not _text(actual_origin_main):
        blockers.append("source_origin_main_unavailable")
    if source_freeze.get("git_head_sha") != actual_head:
        blockers.append("source_git_head_mismatch")
    if source_freeze.get("origin_main_sha") != actual_origin_main:
        blockers.append("source_origin_main_mismatch")
    governance_mode = _text(_mapping(payload.get("governance")).get("governance_mode"))
    if governance_mode == "solo_developer_controlled":
        if source_freeze.get("integration_state") != "frozen_dedicated_branch_commit":
            blockers.append("solo_source_integration_state_not_frozen")
        if source_freeze.get("unmerged_execution_is_internal_only") is not True:
            blockers.append("solo_unmerged_execution_scope_not_restricted")
    elif actual_head != actual_origin_main:
        blockers.append("source_head_is_not_origin_main")
    files = source_freeze.get("files")
    if not isinstance(files, list) or not files:
        blockers.append("source_freeze_files_missing")
        return ""
    declared_paths = {_text(_mapping(item).get("path")) for item in files}
    if declared_paths != _REQUIRED_SOURCE_FREEZE_PATHS or len(files) != len(
        _REQUIRED_SOURCE_FREEZE_PATHS
    ):
        blockers.append("source_freeze_path_set_incomplete")
    status_code, dirty_source_rows = _git(
        repo_root, "status", "--porcelain", "--", *sorted(_REQUIRED_SOURCE_FREEZE_PATHS)
    )
    if status_code != 0:
        blockers.append("source_worktree_status_unavailable")
    elif dirty_source_rows:
        blockers.append("source_freeze_paths_not_clean")
    verified_rows: list[dict[str, str]] = []
    for index, item in enumerate(files):
        row = _mapping(item)
        path = _resolve_repo_file(repo_root, row.get("path"))
        expected = _text(row.get("sha256"))
        if path is None or not path.is_file():
            blockers.append(f"source_freeze_file_missing:{index}")
            continue
        actual = _sha256_path(path)
        if expected != actual:
            blockers.append(f"source_freeze_hash_mismatch:{row.get('path', index)}")
        verified_rows.append({"path": str(row.get("path")), "sha256": actual})
    return hashlib.sha256(_canonical_bytes(verified_rows)).hexdigest()


def _validate_environment(
    payload: Mapping[str, Any],
    repo_root: Path,
    gnina_path: Path | None,
    native_backend_snapshot: Mapping[str, Any] | None,
    blockers: list[str],
) -> None:
    environment = _mapping(payload.get("environment_freeze"))
    actual_versions = {
        "python": platform.python_version(),
        "torch": _distribution_version("torch"),
        "rdkit": _distribution_version("rdkit-pypi"),
        "posebusters": _distribution_version("posebusters"),
    }
    expected_versions = _mapping(environment.get("versions"))
    for name, actual in actual_versions.items():
        if expected_versions.get(name) != actual:
            blockers.append(f"environment_version_mismatch:{name}")
    cpu_policy = _mapping(environment.get("cpu_policy"))
    if cpu_policy != {
        "cpu_count": 1,
        "torch_intraop_threads": 1,
        "torch_interop_threads": 1,
    }:
        blockers.append("cpu_policy_not_frozen")
    if _mapping(environment.get("host")) != current_stage0_host_environment():
        blockers.append("host_environment_mismatch")
    if gnina_path is not None:
        if not gnina_path.is_file():
            blockers.append("gnina_binary_missing")
        elif environment.get("gnina_sha256") != _sha256_path(gnina_path):
            blockers.append("gnina_hash_mismatch")
    elif not _is_sha256(environment.get("gnina_sha256")):
        blockers.append("gnina_hash_not_frozen")

    native = _mapping(environment.get("native_backend"))
    if native.get("backend") != "rust_cpu_required":
        blockers.append("native_backend_not_rust_cpu_required")
    if native.get("distribution_version") != "0.2.0rc5":
        blockers.append("native_backend_version_not_rc5")
    if native.get("thread_count") != 1:
        blockers.append("native_backend_thread_count_not_frozen")
    for field in ("extension_sha256", "cargo_lock_sha256", "wheel_sha256"):
        if not _is_sha256(native.get(field)):
            blockers.append(f"native_backend_{field}_invalid")
    for field in ("rustc_version", "target_triple", "build_flags"):
        if not _text(native.get(field)):
            blockers.append(f"native_backend_{field}_missing")
    _validate_bound_artifact(
        native,
        repo_root=repo_root,
        path_field="wheel_path",
        sha_field="wheel_sha256",
        blocker_prefix="native_wheel",
        blockers=blockers,
    )
    cargo_lock = repo_root / "rust_engine_v2/Cargo.lock"
    if cargo_lock.is_file() and native.get("cargo_lock_sha256") != _sha256_path(
        cargo_lock
    ):
        blockers.append("native_backend_cargo_lock_mismatch")
    observed = _mapping(native_backend_snapshot)
    for field in (
        "backend",
        "distribution_version",
        "extension_sha256",
        "cargo_lock_sha256",
        "rustc_version",
        "target_triple",
        "build_flags",
        "thread_count",
    ):
        if native.get(field) != observed.get(field):
            blockers.append(f"native_backend_runtime_mismatch:{field}")


def _validate_artifacts_and_suite(
    payload: Mapping[str, Any],
    repo_root: Path,
    output_root: Path | None,
    blockers: list[str],
) -> None:
    artifacts = _mapping(payload.get("artifact_retention"))
    expected_counts = {
        "engine_case_rows": STAGE0_ENGINE_ROW_COUNT,
        "engine_v2_candidate_diagnostic_slots": (
            STAGE0_CANDIDATE_DIAGNOSTIC_SLOT_COUNT
        ),
    }
    for name, expected in expected_counts.items():
        if artifacts.get(name) != expected:
            blockers.append(f"artifact_count_not_frozen:{name}")
    required_retention_flags = {
        "retain_poses",
        "retain_logs",
        "retain_receipts",
        "retain_candidate_diagnostics",
        "retain_fresh_128_report",
        "retain_historical_300_development_report",
        "retain_environment_snapshot",
        "retain_source_freeze",
        "retain_external_binary_and_version_log",
        "retain_infrastructure_failure_report",
        "retain_result_review_receipt",
        "sha256_manifest_required",
        "owner_only_permissions_required",
        "partial_results_nonclaimable",
        "cache_cannot_promote_partial_results",
        "retain_until_independent_review_complete",
    }
    for field in sorted(required_retention_flags):
        if artifacts.get(field) is not True:
            blockers.append(f"artifact_retention_missing:{field}")
    retention_root = _text(artifacts.get("retention_root"))
    if not retention_root.startswith(".betelgeuze/"):
        blockers.append("artifact_retention_root_invalid")
    expected_output_root = (repo_root / retention_root).resolve()
    if output_root is None:
        blockers.append("artifact_output_root_not_verified")
    elif output_root.resolve() != expected_output_root:
        blockers.append("artifact_output_root_mismatch")
    capacity = artifacts.get("minimum_free_bytes_before_run")
    if type(capacity) is not int or capacity < 1:
        blockers.append("artifact_capacity_preflight_not_frozen")
    elif shutil.disk_usage(repo_root).free < capacity:
        blockers.append("artifact_capacity_preflight_failed")

    suite = _mapping(payload.get("full_suite_classification"))
    historical = _mapping(suite.get("historical_pr_run"))
    if historical != {"failed": 216, "errors": 3}:
        blockers.append("full_suite_historical_counts_not_bound")
    current = _mapping(suite.get("current_reproduction"))
    current_failed = current.get("failed")
    current_errors = current.get("errors")
    if (
        type(current_failed) is not int
        or current_failed < 0
        or type(current_errors) is not int
        or current_errors < 0
    ):
        blockers.append("full_suite_current_counts_invalid")
    counts = _mapping(suite.get("category_counts"))
    if set(counts) != _REQUIRED_SUITE_CATEGORIES:
        blockers.append("full_suite_categories_incomplete")
    elif any(type(value) is not int or value < 0 for value in counts.values()):
        blockers.append("full_suite_category_counts_invalid")
    elif (
        type(current_failed) is int
        and type(current_errors) is int
        and sum(counts.values()) != current_failed + current_errors
    ):
        blockers.append("full_suite_classification_total_mismatch")
    if suite.get("all_outcomes_classified") is not True:
        blockers.append("full_suite_outcomes_unclassified")
    if suite.get("unclassified_count") != 0:
        blockers.append("full_suite_unclassified_count_nonzero")
    if suite.get("actual_regression_review_complete") is not True:
        blockers.append("actual_regression_review_incomplete")
    if suite.get("engine_v2_required_suite_green") is not True:
        blockers.append("engine_v2_required_suite_not_green")
    if suite.get("official_tier_definitions_frozen") is not True:
        blockers.append("official_tier_definitions_not_frozen")
    if suite.get("execution_boundary") not in {
        "monorepo_green",
        "official_tiered_suites",
    }:
        blockers.append("full_suite_execution_boundary_not_frozen")
    if not _is_sha256(suite.get("classification_receipt_sha256")):
        blockers.append("full_suite_classification_receipt_missing")
    _validate_bound_artifact(
        suite,
        repo_root=repo_root,
        path_field="classification_receipt_path",
        sha_field="classification_receipt_sha256",
        blocker_prefix="full_suite_classification",
        blockers=blockers,
    )
    receipt_path = _resolve_repo_file(
        repo_root, suite.get("classification_receipt_path")
    )
    receipt = _read_json_object(receipt_path)
    receipt_without_hash = dict(receipt)
    receipt_self_hash = receipt_without_hash.pop("receipt_sha256", None)
    if receipt.get("schema_id") != (
        "betelgeuze.engine_v2_stage0_full_suite_classification/1.0.0"
    ):
        blockers.append("full_suite_classification_schema_invalid")
    if (
        receipt_self_hash
        != hashlib.sha256(_canonical_bytes(receipt_without_hash)).hexdigest()
    ):
        blockers.append("full_suite_classification_self_hash_invalid")
    if _mapping(receipt.get("historical_pr_run")) != historical:
        blockers.append("full_suite_historical_receipt_mismatch")
    expected_current = {
        "failed": current_failed,
        "errors": current_errors,
        "nonpassing_total": (
            current_failed + current_errors
            if type(current_failed) is int and type(current_errors) is int
            else -1
        ),
    }
    if _mapping(receipt.get("current_reproduction")) != expected_current:
        blockers.append("full_suite_current_receipt_mismatch")
    if _mapping(receipt.get("category_counts")) != counts:
        blockers.append("full_suite_category_receipt_mismatch")
    if receipt.get("all_outcomes_classified") is not True:
        blockers.append("full_suite_receipt_has_unclassified_outcomes")
    rows = receipt.get("rows")
    expected_nonpassing_total = expected_current["nonpassing_total"]
    if not isinstance(rows, list) or len(rows) != expected_nonpassing_total:
        blockers.append("full_suite_receipt_row_count_mismatch")
    else:
        row_categories: Counter[str] = Counter()
        row_kinds: Counter[str] = Counter()
        required_row_fields = {
            "category",
            "classname",
            "kind",
            "message_sha256",
            "name",
            "rule_id",
        }
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != required_row_fields:
                blockers.append("full_suite_receipt_row_schema_invalid")
                continue
            category = _text(row.get("category"))
            kind = _text(row.get("kind"))
            if category not in _REQUIRED_SUITE_CATEGORIES:
                blockers.append("full_suite_receipt_row_category_invalid")
            else:
                row_categories[category] += 1
            if kind not in {"failure", "error"}:
                blockers.append("full_suite_receipt_row_kind_invalid")
            else:
                row_kinds[kind] += 1
            if not _text(row.get("classname")) or not _text(row.get("name")):
                blockers.append("full_suite_receipt_row_identity_invalid")
            if not _text(row.get("rule_id")):
                blockers.append("full_suite_receipt_row_rule_invalid")
            if not _is_sha256(row.get("message_sha256")):
                blockers.append("full_suite_receipt_row_message_hash_invalid")
        if {
            category: row_categories.get(category, 0)
            for category in _REQUIRED_SUITE_CATEGORIES
        } != dict(counts):
            blockers.append("full_suite_receipt_row_category_counts_mismatch")
        if row_kinds != Counter({"failure": current_failed, "error": current_errors}):
            blockers.append("full_suite_receipt_row_kind_counts_mismatch")
    if not _is_sha256(receipt.get("source_junit_sha256")):
        blockers.append("full_suite_receipt_junit_hash_invalid")
    if _mapping(receipt.get("historical_delta")) != {"failed": -1, "errors": 0}:
        blockers.append("full_suite_receipt_historical_delta_mismatch")
    if receipt.get("recommended_execution_boundary") != suite.get("execution_boundary"):
        blockers.append("full_suite_boundary_receipt_mismatch")

    historical_reproduction = _mapping(suite.get("historical_reproduction"))
    if historical_reproduction != {"failed": 215, "errors": 3}:
        blockers.append("historical_full_suite_reproduction_not_bound")
    if suite.get("historical_count_reconciliation_review_complete") is not True:
        blockers.append("historical_full_suite_reconciliation_review_incomplete")
    if suite.get("historical_count_disposition") != (
        "declared_pr_aggregate_unreproducible_and_non_authoritative"
    ):
        blockers.append("historical_full_suite_disposition_not_frozen")
    if not _is_sha256(suite.get("reconciliation_receipt_sha256")):
        blockers.append("historical_full_suite_reconciliation_receipt_missing")
    _validate_bound_artifact(
        suite,
        repo_root=repo_root,
        path_field="reconciliation_receipt_path",
        sha_field="reconciliation_receipt_sha256",
        blocker_prefix="historical_full_suite_reconciliation",
        blockers=blockers,
    )
    reconciliation_path = _resolve_repo_file(
        repo_root, suite.get("reconciliation_receipt_path")
    )
    reconciliation = _read_json_object(reconciliation_path)
    reconciliation_without_hash = dict(reconciliation)
    reconciliation_self_hash = reconciliation_without_hash.pop("receipt_sha256", None)
    if reconciliation.get("schema_id") != (
        "betelgeuze.engine_v2_stage0_full_suite_reconciliation/1.0.0"
    ):
        blockers.append("historical_full_suite_reconciliation_schema_invalid")
    if (
        reconciliation_self_hash
        != hashlib.sha256(_canonical_bytes(reconciliation_without_hash)).hexdigest()
    ):
        blockers.append("historical_full_suite_reconciliation_self_hash_invalid")
    if _mapping(reconciliation.get("declared_pr_counts")) != historical:
        blockers.append("historical_full_suite_declared_counts_mismatch")
    if reconciliation.get("historical_source_commit_sha") != (
        STAGE0_DIAGNOSTIC_REVIEW_HEAD_SHA
    ):
        blockers.append("historical_full_suite_source_commit_mismatch")
    if _mapping(reconciliation.get("historical_reproduction")) != (
        historical_reproduction
    ):
        blockers.append("historical_full_suite_reproduction_receipt_mismatch")
    if _mapping(reconciliation.get("current_reproduction")) != current:
        blockers.append("historical_full_suite_current_receipt_mismatch")
    if reconciliation.get("unresolved_declared_failure_count") != 1:
        blockers.append("historical_full_suite_unresolved_count_mismatch")
    if reconciliation.get("declared_aggregate_reproduced") is not False:
        blockers.append("historical_full_suite_reproduction_claim_invalid")
    if reconciliation.get("historical_and_current_row_multisets_equal") is not True:
        blockers.append("historical_full_suite_row_multisets_differ")
    if reconciliation.get("only_historical_rows") != []:
        blockers.append("historical_full_suite_has_unmatched_historical_rows")
    if reconciliation.get("only_current_rows") != []:
        blockers.append("historical_full_suite_has_unmatched_current_rows")
    if reconciliation.get("review_required") is not True:
        blockers.append("historical_full_suite_reconciliation_review_not_required")


def _validate_independent_governance(
    payload: Mapping[str, Any], repo_root: Path, blockers: list[str]
) -> tuple[str, str, str, bool]:
    governance = _mapping(payload.get("governance"))
    author = _text(governance.get("contract_author_id"))
    reviewer = _text(governance.get("independent_reviewer_id"))
    operator = _text(governance.get("blind_operator_id"))
    if not author or not reviewer or not operator:
        blockers.append("governance_roles_unassigned")
    elif len({author, reviewer, operator}) != 3:
        blockers.append("governance_roles_not_independent")
    for field in (
        "contract_review_approved",
        "scientific_boundary_review_approved",
        "legal_and_license_review_approved",
        "operator_runbook_accepted",
        "historical_216_3_reconciliation_approved",
        "full_suite_classification_review_approved",
        "suite_boundaries_approved",
        "ci_authority_review_approved",
    ):
        if governance.get(field) is not True:
            blockers.append(f"governance_approval_missing:{field}")
    if not _is_sha256(governance.get("independent_attestation_sha256")):
        blockers.append("independent_attestation_missing")
    _validate_bound_artifact(
        governance,
        repo_root=repo_root,
        path_field="independent_attestation_path",
        sha_field="independent_attestation_sha256",
        blocker_prefix="independent_attestation",
        blockers=blockers,
    )
    if governance.get("primary_holdout_unopened_confirmed") is not True:
        blockers.append("primary_holdout_unopened_not_attested")
    if governance.get("thresholds_frozen_before_execution_confirmed") is not True:
        blockers.append("preexecution_threshold_freeze_not_attested")
    if governance.get("github_pr_211_merged_confirmed") is not True:
        blockers.append("github_pr_211_merge_not_attested")
    if governance.get("github_issue_199_status_updated_confirmed") is not True:
        blockers.append("github_issue_199_update_not_attested")
    if not _valid_utc_timestamp(governance.get("frozen_at_utc")):
        blockers.append("freeze_timestamp_invalid")
    if governance.get("product_execution_enabled") is not False:
        blockers.append("product_execution_must_remain_disabled")
    attestation_path = _resolve_repo_file(
        repo_root, governance.get("independent_attestation_path")
    )
    attestation = _read_json_object(attestation_path)
    if attestation.get("schema_id") != (
        "betelgeuze.engine_v2_stage0_independent_attestation/1.0.0"
    ):
        blockers.append("independent_attestation_schema_invalid")
    if attestation.get("review_subject_sha256") != (
        compute_stage0_review_subject_sha256(payload)
    ):
        blockers.append("independent_attestation_subject_mismatch")
    if attestation.get("contract_author_id") != author:
        blockers.append("independent_attestation_author_mismatch")
    if attestation.get("independent_reviewer_id") != reviewer:
        blockers.append("independent_attestation_reviewer_mismatch")
    if attestation.get("blind_operator_id") != operator:
        blockers.append("independent_attestation_operator_mismatch")
    decisions = _mapping(attestation.get("decisions"))
    required_decisions = {
        "contract_review_approved",
        "scientific_boundary_review_approved",
        "legal_and_license_review_approved",
        "operator_runbook_accepted",
        "primary_holdout_unopened_confirmed",
        "thresholds_frozen_before_execution_confirmed",
        "github_pr_211_merged_confirmed",
        "github_issue_199_status_updated_confirmed",
        "historical_216_3_reconciliation_approved",
        "full_suite_classification_review_approved",
        "suite_boundaries_approved",
        "ci_authority_review_approved",
    }
    if set(decisions) != required_decisions or any(
        decisions.get(field) is not True for field in required_decisions
    ):
        blockers.append("independent_attestation_decisions_incomplete")
    if not _valid_utc_timestamp(attestation.get("attested_at_utc")):
        blockers.append("independent_attestation_timestamp_invalid")
    return reviewer, operator, "independent_three_role", True


_SOLO_REQUIRED_DECISIONS = {
    "ci_authority_self_review_completed",
    "contract_self_review_completed",
    "full_suite_classification_self_review_completed",
    "historical_216_3_reconciliation_self_review_completed",
    "legal_and_license_self_review_completed",
    "native_parity_gate_verified",
    "operator_runbook_self_review_completed",
    "primary_holdout_unopened_confirmed",
    "run_once_no_tuning_policy_accepted",
    "scientific_boundary_self_review_completed",
    "source_freeze_verified",
    "suite_boundaries_self_review_completed",
    "thresholds_frozen_before_execution_confirmed",
}
_SOLO_REQUIRED_BOOLEAN_CONTROLS = {
    "automated_policy_verifier_required",
    "clean_frozen_commit_required",
    "external_review_required_before_public_claim",
    "immutable_artifact_manifest_required",
    "post_result_retuning_forbidden",
    "two_pass_self_review_required",
}
_SOLO_REVIEW_SCHEMA_ID = "betelgeuze.engine_v2_stage0_solo_self_review_pass/1.2.0"
_SOLO_OPERATIONAL_SCHEMA_ID = (
    "betelgeuze.engine_v2_stage0_solo_operational_evidence/1.0.0"
)


def _self_hash_matches(payload: Mapping[str, Any], field: str) -> bool:
    projection = dict(payload)
    observed = projection.pop(field, None)
    return observed == hashlib.sha256(_canonical_bytes(projection)).hexdigest()


def _validate_solo_review_artifacts(
    payload: Mapping[str, Any],
    governance: Mapping[str, Any],
    *,
    repo_root: Path,
    developer: str,
    decisions: Mapping[str, Any],
    blockers: list[str],
) -> tuple[list[Any], Mapping[str, Any]]:
    rows = governance.get("solo_review_passes")
    if not isinstance(rows, list) or len(rows) != 2:
        blockers.append("solo_review_pass_artifacts_incomplete")
        rows = []
    reviews: list[Mapping[str, Any]] = []
    source_commit = _text(_mapping(payload.get("source_freeze")).get("git_head_sha"))
    for expected_pass in (1, 2):
        row = _mapping(rows[expected_pass - 1] if len(rows) == 2 else None)
        prefix = f"solo_review_pass_{expected_pass}"
        if row.get("review_pass") != expected_pass:
            blockers.append(f"{prefix}_index_mismatch")
        _validate_bound_artifact(
            row,
            repo_root=repo_root,
            path_field="path",
            sha_field="file_sha256",
            blocker_prefix=prefix,
            blockers=blockers,
        )
        path = _resolve_repo_file(repo_root, row.get("path"))
        review = _read_json_object(path)
        projection = dict(review)
        receipt_sha256 = projection.pop("receipt_sha256", None)
        if receipt_sha256 != hashlib.sha256(_canonical_bytes(projection)).hexdigest():
            blockers.append(f"{prefix}_self_hash_invalid")
        if row.get("receipt_sha256") != receipt_sha256:
            blockers.append(f"{prefix}_receipt_hash_mismatch")
        if review.get("schema_id") != _SOLO_REVIEW_SCHEMA_ID:
            blockers.append(f"{prefix}_schema_invalid")
        if review.get("review_pass") != expected_pass:
            blockers.append(f"{prefix}_payload_index_mismatch")
        if review.get("developer_id") != developer:
            blockers.append(f"{prefix}_developer_mismatch")
        if review.get("source_freeze_commit_sha") != source_commit:
            blockers.append(f"{prefix}_source_commit_mismatch")
        if review.get("source_worktree_clean") is not True:
            blockers.append(f"{prefix}_source_not_clean")
        if review.get("fresh_internal_blind_holdout_executed") is not False:
            blockers.append(f"{prefix}_holdout_already_opened")
        if _mapping(review.get("self_review_decisions")) != decisions:
            blockers.append(f"{prefix}_decisions_mismatch")
        gate_results = _mapping(review.get("development_gate_results"))
        if set(gate_results) != set(_REQUIRED_THRESHOLDS) or any(
            gate_results.get(name) != "pass" for name in _REQUIRED_THRESHOLDS
        ):
            blockers.append(f"{prefix}_development_gates_not_passed")
        if row.get("reviewed_at_utc") != review.get("reviewed_at_utc"):
            blockers.append(f"{prefix}_timestamp_mismatch")
        reviews.append(review)

    reviewed_evidence = _mapping(governance.get("reviewed_evidence"))
    if len(reviews) == 2:
        first_evidence = _mapping(reviews[0].get("reviewed_evidence"))
        second_evidence = _mapping(reviews[1].get("reviewed_evidence"))
        if not first_evidence or first_evidence != second_evidence:
            blockers.append("solo_review_pass_evidence_mismatch")
        if reviewed_evidence != second_evidence:
            blockers.append("solo_governance_reviewed_evidence_mismatch")
        expected_previous = {
            "path": _mapping(rows[0]).get("path") if len(rows) == 2 else None,
            "file_sha256": (
                _mapping(rows[0]).get("file_sha256") if len(rows) == 2 else None
            ),
            "receipt_sha256": reviews[0].get("receipt_sha256"),
            "reviewed_at_utc": reviews[0].get("reviewed_at_utc"),
        }
        if _mapping(reviews[1].get("previous_review_pass")) != expected_previous:
            blockers.append("solo_review_previous_pass_chain_mismatch")
        first_timestamp = _utc_datetime(reviews[0].get("reviewed_at_utc"))
        second_timestamp = _utc_datetime(reviews[1].get("reviewed_at_utc"))
        if (
            first_timestamp is None
            or second_timestamp is None
            or (second_timestamp - first_timestamp).total_seconds() < 24 * 3600
        ):
            blockers.append("solo_review_artifacts_not_time_separated")
        if reviews[0].get("reviewed_at_utc") != governance.get(
            "first_self_reviewed_at_utc"
        ) or reviews[1].get("reviewed_at_utc") != governance.get(
            "second_self_reviewed_at_utc"
        ):
            blockers.append("solo_review_artifact_governance_timestamp_mismatch")

    artifact_specs = (
        (
            "operational_evidence_path",
            "operational_evidence_file_sha256",
            "operational_evidence",
            True,
        ),
        (
            "scorer_term_development_report_path",
            "scorer_term_development_report_file_sha256",
            "development_report",
            False,
        ),
        (
            "threshold_evidence_path",
            "threshold_evidence_file_sha256",
            "threshold_evidence",
            True,
        ),
        ("base_wheel_path", "base_wheel_sha256", "base_wheel", False),
        (
            "native_wheel_path",
            "native_cp310_wheel_sha256",
            "native_wheel",
            False,
        ),
    )
    for path_field, hash_field, label, required in artifact_specs:
        present = path_field in reviewed_evidence or hash_field in reviewed_evidence
        if required and not present:
            blockers.append(f"solo_reviewed_{label}_missing")
        if not present:
            continue
        _validate_bound_artifact(
            reviewed_evidence,
            repo_root=repo_root,
            path_field=path_field,
            sha_field=hash_field,
            blocker_prefix=f"solo_reviewed_{label}",
            blockers=blockers,
        )

    operational_path = _resolve_repo_file(
        repo_root, reviewed_evidence.get("operational_evidence_path")
    )
    operational = _read_json_object(operational_path)
    if operational.get("schema_id") != _SOLO_OPERATIONAL_SCHEMA_ID:
        blockers.append("solo_reviewed_operational_evidence_schema_invalid")
    if not _self_hash_matches(operational, "receipt_sha256"):
        blockers.append("solo_reviewed_operational_evidence_self_hash_invalid")
    if reviewed_evidence.get("operational_evidence_receipt_sha256") != operational.get(
        "receipt_sha256"
    ):
        blockers.append("solo_reviewed_operational_evidence_receipt_mismatch")
    if operational.get("developer_id") != developer:
        blockers.append("solo_reviewed_operational_evidence_developer_mismatch")

    threshold_path = _resolve_repo_file(
        repo_root, reviewed_evidence.get("threshold_evidence_path")
    )
    threshold = _read_json_object(threshold_path)
    if threshold.get("schema_id") != _THRESHOLD_EVIDENCE_SCHEMA_ID:
        blockers.append("solo_reviewed_threshold_evidence_schema_invalid")
    if not _self_hash_matches(threshold, "evidence_sha256"):
        blockers.append("solo_reviewed_threshold_evidence_self_hash_invalid")
    if reviewed_evidence.get("threshold_evidence_sha256") != threshold.get(
        "evidence_sha256"
    ):
        blockers.append("solo_reviewed_threshold_evidence_receipt_mismatch")

    return rows, reviewed_evidence


def _validate_solo_governance(
    payload: Mapping[str, Any], repo_root: Path, blockers: list[str]
) -> tuple[str, str, str, bool]:
    governance = _mapping(payload.get("governance"))
    developer = _text(governance.get("developer_id"))
    operator = _text(governance.get("blind_operator_id"))
    if not developer or operator != developer:
        blockers.append("solo_governance_identity_invalid")
    if _text(governance.get("independent_reviewer_id")):
        blockers.append("solo_governance_must_not_claim_independent_reviewer")
    if governance.get("independent_review_complete") is not False:
        blockers.append("solo_governance_independent_review_must_be_false")
    if governance.get("execution_scope") != "internal_provisional_evidence_only":
        blockers.append("solo_execution_scope_not_restricted")
    for field in (
        "public_claims_allowed",
        "product_promotion_allowed",
        "product_execution_enabled",
    ):
        if governance.get(field) is not False:
            blockers.append(f"solo_governance_false_boundary_missing:{field}")

    decisions = _mapping(governance.get("self_review_decisions"))
    if set(decisions) != _SOLO_REQUIRED_DECISIONS or any(
        decisions.get(field) is not True for field in _SOLO_REQUIRED_DECISIONS
    ):
        blockers.append("solo_self_review_decisions_incomplete")
    controls = _mapping(governance.get("compensating_controls"))
    expected_control_fields = {
        *_SOLO_REQUIRED_BOOLEAN_CONTROLS,
        "review_pass_minimum_separation_hours",
    }
    if set(controls) != expected_control_fields:
        blockers.append("solo_compensating_controls_incomplete")
    for field in _SOLO_REQUIRED_BOOLEAN_CONTROLS:
        if controls.get(field) is not True:
            blockers.append(f"solo_compensating_control_missing:{field}")
    minimum_hours = controls.get("review_pass_minimum_separation_hours")
    if type(minimum_hours) is not int or minimum_hours < 24:
        blockers.append("solo_review_separation_policy_too_short")

    first_review = _utc_datetime(governance.get("first_self_reviewed_at_utc"))
    second_review = _utc_datetime(governance.get("second_self_reviewed_at_utc"))
    frozen_at = _utc_datetime(governance.get("frozen_at_utc"))
    if first_review is None or second_review is None or frozen_at is None:
        blockers.append("solo_review_timestamps_invalid")
    elif (
        type(minimum_hours) is int
        and (second_review - first_review).total_seconds() < minimum_hours * 3600
    ):
        blockers.append("solo_review_passes_not_time_separated")
    elif not first_review <= second_review <= frozen_at:
        blockers.append("solo_review_timestamp_order_invalid")

    review_passes, reviewed_evidence = _validate_solo_review_artifacts(
        payload,
        governance,
        repo_root=repo_root,
        developer=developer,
        decisions=decisions,
        blockers=blockers,
    )

    if not _is_sha256(governance.get("solo_attestation_sha256")):
        blockers.append("solo_attestation_missing")
    _validate_bound_artifact(
        governance,
        repo_root=repo_root,
        path_field="solo_attestation_path",
        sha_field="solo_attestation_sha256",
        blocker_prefix="solo_attestation",
        blockers=blockers,
    )
    attestation_path = _resolve_repo_file(
        repo_root, governance.get("solo_attestation_path")
    )
    attestation = _read_json_object(attestation_path)
    if attestation.get("schema_id") != (
        "betelgeuze.engine_v2_stage0_solo_attestation/1.0.0"
    ):
        blockers.append("solo_attestation_schema_invalid")
    if attestation.get("review_subject_sha256") != (
        compute_stage0_review_subject_sha256(payload)
    ):
        blockers.append("solo_attestation_subject_mismatch")
    if attestation.get("developer_id") != developer:
        blockers.append("solo_attestation_developer_mismatch")
    if attestation.get("blind_operator_id") != operator:
        blockers.append("solo_attestation_operator_mismatch")
    if _mapping(attestation.get("self_review_decisions")) != decisions:
        blockers.append("solo_attestation_decisions_mismatch")
    if _mapping(attestation.get("compensating_controls")) != controls:
        blockers.append("solo_attestation_controls_mismatch")
    if attestation.get("solo_review_passes") != review_passes:
        blockers.append("solo_attestation_review_passes_mismatch")
    if _mapping(attestation.get("reviewed_evidence")) != reviewed_evidence:
        blockers.append("solo_attestation_reviewed_evidence_mismatch")
    if attestation.get("independent_review_complete") is not False:
        blockers.append("solo_attestation_independence_claim_invalid")
    if attestation.get("external_review_required_before_public_claim") is not True:
        blockers.append("solo_attestation_external_claim_gate_missing")
    if not _valid_utc_timestamp(attestation.get("attested_at_utc")):
        blockers.append("solo_attestation_timestamp_invalid")
    return developer, operator, "solo_developer_controlled", False


def _validate_governance(
    payload: Mapping[str, Any], repo_root: Path, blockers: list[str]
) -> tuple[str, str, str, bool]:
    mode = _text(_mapping(payload.get("governance")).get("governance_mode"))
    if mode == "solo_developer_controlled":
        return _validate_solo_governance(payload, repo_root, blockers)
    if mode not in {"", "independent_three_role"}:
        blockers.append("governance_mode_unsupported")
    return _validate_independent_governance(payload, repo_root, blockers)


def _validate_ci_authority(
    payload: Mapping[str, Any], repo_root: Path, blockers: list[str]
) -> None:
    policy = _mapping(payload.get("ci_authority"))
    if policy.get("authoritative_workflows") != list(_AUTHORITATIVE_CI_WORKFLOWS):
        blockers.append("ci_authoritative_workflows_not_frozen")
    if policy.get("new_feature_workflow_policy") != (
        "consolidate_into_authoritative_workflows"
    ):
        blockers.append("ci_new_workflow_policy_not_frozen")
    if policy.get("specialized_workflows_review_complete") is not True:
        blockers.append("ci_specialized_workflow_review_incomplete")
    if policy.get("issue_199_status_reviewed") is not True:
        blockers.append("github_issue_199_status_unreviewed")
    if policy.get("issue_199_state_at_freeze") not in {"open", "closed"}:
        blockers.append("github_issue_199_state_not_frozen")
    if not _is_sha256(policy.get("inventory_receipt_sha256")):
        blockers.append("ci_inventory_receipt_hash_missing")
    _validate_bound_artifact(
        policy,
        repo_root=repo_root,
        path_field="inventory_receipt_path",
        sha_field="inventory_receipt_sha256",
        blocker_prefix="ci_inventory",
        blockers=blockers,
    )
    receipt_path = _resolve_repo_file(repo_root, policy.get("inventory_receipt_path"))
    receipt = _read_json_object(receipt_path)
    receipt_without_hash = dict(receipt)
    receipt_self_hash = receipt_without_hash.pop("receipt_sha256", None)
    if receipt.get("schema_id") != (
        "betelgeuze.engine_v2_ci_authority_inventory/1.0.0"
    ):
        blockers.append("ci_inventory_schema_invalid")
    if (
        receipt_self_hash
        != hashlib.sha256(_canonical_bytes(receipt_without_hash)).hexdigest()
    ):
        blockers.append("ci_inventory_self_hash_invalid")
    workflow_root = repo_root / ".github/workflows"
    current_workflows = tuple(
        sorted(
            path.relative_to(repo_root).as_posix()
            for path in workflow_root.glob("ci-engine-v2-*.yml")
            if path.is_file()
        )
    )
    current_hashes = {
        path: _sha256_path(repo_root / path) for path in current_workflows
    }
    specialized = [
        path for path in current_workflows if path not in _AUTHORITATIVE_CI_WORKFLOWS
    ]
    if receipt.get("workflow_count") != len(current_workflows):
        blockers.append("ci_inventory_workflow_count_mismatch")
    if receipt.get("authoritative_workflows") != list(_AUTHORITATIVE_CI_WORKFLOWS):
        blockers.append("ci_inventory_authoritative_set_mismatch")
    if receipt.get("specialized_workflows") != specialized:
        blockers.append("ci_inventory_specialized_set_mismatch")
    if _mapping(receipt.get("workflow_sha256s")) != current_hashes:
        blockers.append("ci_inventory_workflow_hash_mismatch")
    if receipt.get("stage0_tests_in_authoritative_main") is not True:
        blockers.append("ci_authoritative_main_missing_stage0_tests")
    if receipt.get("specialized_workflows_hidden") is not False:
        blockers.append("ci_inventory_hides_specialized_workflows")


def verify_stage0_admission(
    policy_path: Path,
    *,
    repo_root: Path,
    gnina_path: Path | None = None,
    output_root: Path | None = None,
) -> VerifiedStage0Admission:
    """Verify all Stage 0 gates without reading benchmark results."""

    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Stage0AdmissionError(("stage0_policy_unreadable",)) from exc
    if not isinstance(payload, dict):
        raise Stage0AdmissionError(("stage0_policy_not_object",))

    blockers: list[str] = []
    if payload.get("schema_version") != STAGE0_SCHEMA_VERSION:
        blockers.append("stage0_schema_version_mismatch")
    if payload.get("protocol_id") != STAGE0_PROTOCOL_ID:
        blockers.append("stage0_protocol_id_mismatch")
    if payload.get("diagnostic_contract_id") != STAGE0_DIAGNOSTIC_CONTRACT_ID:
        blockers.append("diagnostic_contract_not_rc5")
    if payload.get("freeze_status") != "frozen_before_primary_execution":
        blockers.append("stage0_policy_not_frozen")
    partition = _mapping(payload.get("partition"))
    if partition != {
        "source_total": STAGE0_TOTAL_CASE_COUNT,
        "historical_development": STAGE0_DEVELOPMENT_CASE_COUNT,
        "fresh_internal_blind_holdout": STAGE0_PRIMARY_CASE_COUNT,
    }:
        blockers.append("blind_partition_mismatch")

    _validate_thresholds(payload, repo_root, blockers)
    _validate_baselines(payload, repo_root, blockers)
    _validate_branching(payload, blockers)
    _validate_contamination_registry(repo_root, blockers)
    source_sha256 = _validate_source_freeze(payload, repo_root, blockers)
    try:
        native_backend_snapshot = current_stage0_native_backend()
    except (ImportError, OSError, Stage0AdmissionError) as exc:
        blockers.append(f"native_backend_unavailable:{type(exc).__name__}")
        native_backend_snapshot = {}
    _validate_environment(
        payload,
        repo_root,
        gnina_path,
        native_backend_snapshot,
        blockers,
    )
    _validate_artifacts_and_suite(payload, repo_root, output_root, blockers)
    reviewer, operator, governance_mode, independent_review_complete = (
        _validate_governance(payload, repo_root, blockers)
    )
    _validate_ci_authority(payload, repo_root, blockers)

    expected_policy_sha256 = compute_stage0_policy_sha256(payload)
    if payload.get("policy_sha256") != expected_policy_sha256:
        blockers.append("stage0_policy_self_hash_mismatch")
    if blockers:
        raise Stage0AdmissionError(tuple(dict.fromkeys(blockers)))
    return VerifiedStage0Admission(
        policy_sha256=expected_policy_sha256,
        source_freeze_sha256=source_sha256,
        reviewer_id=reviewer,
        operator_id=operator,
        governance_mode=governance_mode,
        independent_review_complete=independent_review_complete,
    )


__all__ = [
    "STAGE0_DIAGNOSTIC_CONTRACT_ID",
    "STAGE0_DIAGNOSTIC_REVIEW_HEAD_SHA",
    "STAGE0_ENGINE_V2_ALGORITHM_PROFILE_ID",
    "STAGE0_PROTOCOL_ID",
    "STAGE0_REQUIRED_SOURCE_FREEZE_PATHS",
    "STAGE0_SCHEMA_VERSION",
    "Stage0AdmissionError",
    "VerifiedStage0Admission",
    "compute_stage0_policy_sha256",
    "compute_stage0_review_subject_sha256",
    "current_stage0_host_environment",
    "current_stage0_native_backend",
    "stage0_engine_v2_algorithm_profile",
    "verify_stage0_admission",
]
