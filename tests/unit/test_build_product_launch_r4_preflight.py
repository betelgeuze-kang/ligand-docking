from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_product_launch_r4_preflight as mod


def _api_flow() -> dict:
    return {
        "summary": {
            "status": "api_customer_flow_release_evidence_ready",
            "formal_release_evidence_ready": True,
            "result_manifest_signature_verified": True,
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    }


def _rollout(**overrides: object) -> dict:
    summary = {
        "status": "product_rollout_execution_readiness_ready",
        "authorized_for_separate_operator_execution": True,
        "blocker_count": 0,
        "approval_tokens_required": [
            "APPROVE_PRODUCT_ROLLOUT",
            "APPROVE_HOSTED_PRODUCT_API_EXPOSURE",
        ],
        "rollout_executed": False,
        "image_pushed": False,
        "service_restarted": False,
        "pager_provider_contacted": False,
        "external_state_mutated": False,
    }
    summary.update(overrides)
    return {"summary": summary}


def _release_bundle() -> dict:
    return {
        "status": "release_bundle_ready_for_operator_review",
        "blocker_count": 0,
        "operator_promotion_policy": {
            "status": "operator_approval_required",
            "external_state_mutation_allowed": False,
            "must_review_fields": ["target", "action", "impact", "risk", "rollback", "verification"],
        },
    }


def _commercial() -> dict:
    return {
        "summary": {
            "status": "product_commercial_independence_gate_ready",
            "blocker_count": 0,
            "license_present": True,
            "commercial_independent_product_claim_allowed": True,
            "general_platform_claim_allowed": False,
            "execution_enabled": False,
            "external_state_mutated": False,
        }
    }


def _license() -> dict:
    return {
        "summary": {
            "status": "product_license_decision_gate_ready",
            "authorized_for_license_file_creation_review": True,
        }
    }


def _third_party() -> dict:
    return {"summary": {"status": "third_party_license_review_gate_ready", "blocker_count": 0, "external_state_mutated": False}}


def _engine() -> dict:
    return {
        "summary": {
            "status": "engine_refinement_tier_ready",
            "engine_refinement_tier_ready": True,
            "check_count": 18,
            "pass_count": 18,
            "blocked_count": 0,
        }
    }


def _build(**overrides: dict) -> dict:
    packets = {
        "api_flow_packet": _api_flow(),
        "rollout_packet": _rollout(),
        "release_bundle_packet": _release_bundle(),
        "commercial_packet": _commercial(),
        "license_packet": _license(),
        "third_party_license_packet": _third_party(),
        "engine_packet": _engine(),
    }
    packets.update(overrides)
    return mod.build_product_launch_r4_preflight(**packets)


def test_product_launch_r4_preflight_ready_but_does_not_execute() -> None:
    payload = _build()
    summary = payload["summary"]

    assert summary["status"] == "product_launch_r4_preflight_ready"
    assert summary["authorized_for_r4_confirmation"] is True
    assert summary["authorized_for_external_mutation"] is False
    assert summary["launch_executed"] is False
    assert summary["external_state_mutated"] is False
    assert summary["pass_count"] == summary["check_count"]
    assert payload["blockers"] == []


def test_product_launch_r4_preflight_blocks_if_rollout_was_already_mutated() -> None:
    payload = _build(rollout_packet=_rollout(rollout_executed=True, external_state_mutated=True))
    blocked = {row["check_id"] for row in payload["blockers"]}

    assert payload["summary"]["status"] == "blocked_product_launch_r4_preflight"
    assert "rollout_execution_preflight_ready" in blocked
    assert "external_mutation_guard_intact" in blocked
    assert payload["summary"]["authorized_for_external_mutation"] is False


def test_product_launch_r4_preflight_blocks_missing_release_policy_field() -> None:
    release = _release_bundle()
    release["operator_promotion_policy"]["must_review_fields"] = ["target", "action"]

    payload = _build(release_bundle_packet=release)

    assert payload["summary"]["status"] == "blocked_product_launch_r4_preflight"
    assert payload["summary"]["blocked_check_ids"] == ["release_bundle_r4_policy_bound"]


def test_product_launch_r4_preflight_cli_writes_outputs(tmp_path: Path) -> None:
    paths = {
        "api": tmp_path / "api.json",
        "rollout": tmp_path / "rollout.json",
        "release": tmp_path / "release.json",
        "commercial": tmp_path / "commercial.json",
        "license": tmp_path / "license.json",
        "third_party": tmp_path / "third_party.json",
        "engine": tmp_path / "engine.json",
    }
    payloads = {
        "api": _api_flow(),
        "rollout": _rollout(),
        "release": _release_bundle(),
        "commercial": _commercial(),
        "license": _license(),
        "third_party": _third_party(),
        "engine": _engine(),
    }
    for name, payload in payloads.items():
        paths[name].write_text(json.dumps(payload) + "\n", encoding="utf-8")
    out_json = tmp_path / "preflight.json"
    out_csv = tmp_path / "preflight.csv"
    out_md = tmp_path / "preflight.md"

    mod.main(
        [
            "--api-flow-json",
            str(paths["api"]),
            "--rollout-json",
            str(paths["rollout"]),
            "--release-bundle-json",
            str(paths["release"]),
            "--commercial-json",
            str(paths["commercial"]),
            "--license-json",
            str(paths["license"]),
            "--third-party-license-json",
            str(paths["third_party"]),
            "--engine-json",
            str(paths["engine"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "product_launch_r4_preflight_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check_id,status,")
    assert "Product Launch R4 Preflight" in out_md.read_text(encoding="utf-8")
