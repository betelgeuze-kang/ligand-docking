from __future__ import annotations

import json
from pathlib import Path

from api.result_manifest import write_result_manifest
from tools.product import build_api_customer_flow_release_evidence as mod


def _signed_manifest(tmp_path: Path) -> tuple[Path, Path]:
    result = tmp_path / "job" / "htvs_summary.json"
    result.parent.mkdir(parents=True)
    result.write_text('{"status":"ok"}\n', encoding="utf-8")
    manifest = tmp_path / "job" / "result_manifest.json"
    write_result_manifest(
        manifest,
        job_id="job_1",
        request={"runner_profile_id": "ligand_htvs_pipeline_default"},
        status="completed",
        result_file=str(result),
        signing_key="tier-alpha-local-smoke-signing-key",
        key_id="tier-alpha-local",
    )
    return result, manifest


def _ready_packets(tmp_path: Path) -> dict[str, dict]:
    result, manifest = _signed_manifest(tmp_path)
    return {
        "e2e": {
            "summary": {
                "status": "api_docking_dispatch_e2e_ready",
                "wiring_ready": True,
                "evidence_mode": "live_job",
            },
            "ledger_worker_state": "completed_fail_closed",
            "simulation_sync_status": "completed",
        },
        "restricted": {
            "summary": {
                "status": "restricted_unattended_execution_runtime_ready",
                "restricted_unattended_execution_ready": True,
                "restricted_unattended_execution_runtime_ready": True,
                "general_platform_claim_allowed": False,
            }
        },
        "smoke": {
            "summary": {
                "status": "tier_alpha_adrb2_dispatch_smoke_pass",
                "evidence_mode": "live_job",
                "api_validated_runner_enabled": True,
            },
            "dispatch_outcome": {
                "dispatched": True,
                "reason": "eligible",
                "enqueue": {"sqlite_status": "submitted"},
            },
            "worker_ran": True,
            "sqlite_job_status": "completed",
            "ledger_worker_state": "completed_fail_closed",
            "simulation_sync_status": "completed",
            "result_file": str(result),
            "result_manifest": str(manifest),
            "result_manifest_exists": True,
            "htvs_summary_exists": True,
        },
        "bundle": {"summary": {"status": "product_bundle_contract_ready", "bundle_validation_passed": True}},
        "delivery": {
            "summary": {
                "status": "product_delivery_evidence_contract_ready",
                "bundle_validation_passed": True,
                "delivery_ready_claim_allowed": True,
            }
        },
        "pilot": {
            "summary": {
                "status": "product_pilot_packet_ready",
                "bundle_validation_passed": True,
                "pilot_delivery_ready": True,
            }
        },
    }


def test_api_customer_flow_release_evidence_ready(tmp_path: Path) -> None:
    packets = _ready_packets(tmp_path)

    payload = mod.build_api_customer_flow_release_evidence(
        e2e_packet=packets["e2e"],
        restricted_packet=packets["restricted"],
        smoke_packet=packets["smoke"],
        product_bundle_packet=packets["bundle"],
        delivery_evidence_packet=packets["delivery"],
        pilot_packet=packets["pilot"],
    )

    summary = payload["summary"]
    assert summary["status"] == "api_customer_flow_release_evidence_ready"
    assert summary["formal_release_evidence_ready"] is True
    assert summary["result_manifest_signature_verified"] is True
    assert summary["bundle_validation_ready"] is True
    assert summary["restricted_unattended_runtime_ready"] is True
    assert payload["blockers"] == []


def test_api_customer_flow_release_evidence_blocks_synthetic_only_e2e(tmp_path: Path) -> None:
    packets = _ready_packets(tmp_path)
    packets["e2e"]["summary"]["evidence_mode"] = "synthetic_wiring_proof"

    payload = mod.build_api_customer_flow_release_evidence(
        e2e_packet=packets["e2e"],
        restricted_packet=packets["restricted"],
        smoke_packet=packets["smoke"],
        product_bundle_packet=packets["bundle"],
        delivery_evidence_packet=packets["delivery"],
        pilot_packet=packets["pilot"],
    )

    assert payload["summary"]["status"] == "blocked_api_customer_flow_release_evidence"
    assert payload["summary"]["blocked_check_ids"] == ["api_dispatch_live_job_ready"]


def test_api_customer_flow_release_evidence_cli_writes_outputs(tmp_path: Path) -> None:
    packets = _ready_packets(tmp_path)
    paths = {name: tmp_path / f"{name}.json" for name in packets}
    for name, packet in packets.items():
        paths[name].write_text(json.dumps(packet) + "\n", encoding="utf-8")
    out_json = tmp_path / "api_flow.json"
    out_csv = tmp_path / "api_flow.csv"
    out_md = tmp_path / "api_flow.md"

    mod.main(
        [
            "--e2e-json",
            str(paths["e2e"]),
            "--restricted-json",
            str(paths["restricted"]),
            "--smoke-json",
            str(paths["smoke"]),
            "--product-bundle-json",
            str(paths["bundle"]),
            "--delivery-evidence-json",
            str(paths["delivery"]),
            "--pilot-json",
            str(paths["pilot"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "api_customer_flow_release_evidence_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("check_id,status,")
    assert "API Customer Flow Release Evidence" in out_md.read_text(encoding="utf-8")
