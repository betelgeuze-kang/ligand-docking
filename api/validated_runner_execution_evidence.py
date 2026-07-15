"""Exact signed purpose binding for validated-runner execution evidence."""

from __future__ import annotations

import re
from typing import Any


EXECUTION_EVIDENCE_SCHEMA_VERSION = "validated_runner_execution_evidence_v1"
EXECUTION_EVIDENCE_PROVENANCE_KEY = "validated_runner_execution_evidence"
EXECUTION_EVIDENCE_PURPOSE_REQUEST_KEY = "execution_evidence_purpose"
EXECUTION_EVIDENCE_SOURCE_ACTOR_REQUEST_KEY = "execution_evidence_source_actor"
TIER_ALPHA_ADRB2_EVIDENCE_PURPOSE = "tier_alpha_adrb2_dispatch_smoke_v1"
TIER_ALPHA_ADRB2_SOURCE_ACTOR = "tier_alpha_dispatch_smoke"
TIER_ALPHA_ADRB2_RUNNER_PROFILE_ID = "ligand_htvs_pipeline_default"
EXECUTION_EVIDENCE_FIELDS = (
    "schema_version",
    "evidence_purpose",
    "source_actor",
    "runner_profile_id",
    "execution_mode",
    "customer_submission_allowed",
    "synthetic_input_allowed",
    "production_claim_allowed",
    "customer_pose_emission_allowed",
    "target_name",
    "family",
    "docking_job_id",
)

_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_PROFILE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_TARGET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
_FAMILY_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _optional_token(value: Any, *, label: str) -> str:
    if type(value) is not str:
        raise ValueError(f"{label} must be a string")
    if value and _TOKEN_RE.fullmatch(value) is None:
        raise ValueError(f"{label} is invalid")
    return value


def _required_match(value: Any, pattern: re.Pattern[str], *, label: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"{label} is invalid")
    return value


def _optional_match(value: Any, pattern: re.Pattern[str], *, label: str) -> str:
    if type(value) is not str or (value and pattern.fullmatch(value) is None):
        raise ValueError(f"{label} is invalid")
    return value


def build_validated_runner_execution_evidence(
    *,
    profile_id: str,
    execution_contract: dict[str, Any],
    request_data: dict[str, Any],
) -> dict[str, Any]:
    params = request_data.get("runner_profile_params")
    if not isinstance(params, dict):
        params = {}
    payload = {
        "schema_version": EXECUTION_EVIDENCE_SCHEMA_VERSION,
        "evidence_purpose": request_data.get(
            EXECUTION_EVIDENCE_PURPOSE_REQUEST_KEY,
            "",
        ),
        "source_actor": request_data.get(
            EXECUTION_EVIDENCE_SOURCE_ACTOR_REQUEST_KEY,
            "",
        ),
        "runner_profile_id": profile_id,
        "execution_mode": execution_contract.get("execution_mode"),
        "customer_submission_allowed": execution_contract.get(
            "customer_submission_allowed"
        ),
        "synthetic_input_allowed": execution_contract.get(
            "synthetic_input_allowed"
        ),
        "production_claim_allowed": execution_contract.get(
            "production_claim_allowed"
        ),
        "customer_pose_emission_allowed": execution_contract.get(
            "customer_pose_emission_allowed"
        ),
        "target_name": request_data.get("target_name", ""),
        "family": params.get("family", ""),
        "docking_job_id": params.get("docking_job_id", ""),
    }
    return validate_validated_runner_execution_evidence(payload)


def tier_alpha_adrb2_execution_evidence(job_id: str) -> dict[str, Any]:
    payload = {
        "schema_version": EXECUTION_EVIDENCE_SCHEMA_VERSION,
        "evidence_purpose": TIER_ALPHA_ADRB2_EVIDENCE_PURPOSE,
        "source_actor": TIER_ALPHA_ADRB2_SOURCE_ACTOR,
        "runner_profile_id": TIER_ALPHA_ADRB2_RUNNER_PROFILE_ID,
        "execution_mode": "smoke",
        "customer_submission_allowed": False,
        "synthetic_input_allowed": True,
        "production_claim_allowed": False,
        "customer_pose_emission_allowed": False,
        "target_name": "ADRB2",
        "family": "gpcr",
        "docking_job_id": job_id,
    }
    return validate_validated_runner_execution_evidence(payload)


def validate_validated_runner_execution_evidence(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(EXECUTION_EVIDENCE_FIELDS):
        raise ValueError("validated runner execution evidence fields are invalid")
    if value["schema_version"] != EXECUTION_EVIDENCE_SCHEMA_VERSION:
        raise ValueError("validated runner execution evidence schema is invalid")
    _optional_token(value["evidence_purpose"], label="evidence_purpose")
    _optional_token(value["source_actor"], label="source_actor")
    _required_match(value["runner_profile_id"], _PROFILE_RE, label="runner_profile_id")
    if value["execution_mode"] not in {"smoke", "restricted-production"}:
        raise ValueError("execution_mode is invalid")
    for field in (
        "customer_submission_allowed",
        "synthetic_input_allowed",
        "production_claim_allowed",
        "customer_pose_emission_allowed",
    ):
        if type(value[field]) is not bool:
            raise ValueError(f"{field} must be an exact boolean")
    _optional_match(value["target_name"], _TARGET_RE, label="target_name")
    _optional_match(value["family"], _FAMILY_RE, label="family")
    _optional_match(value["docking_job_id"], _JOB_ID_RE, label="docking_job_id")
    return {field: value[field] for field in EXECUTION_EVIDENCE_FIELDS}
