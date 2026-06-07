from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_general_protein_ligand_claim_blocker_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _scope_packet() -> dict[str, object]:
    return {
        "summary": {
            "scope_breadth_ready": False,
            "general_protein_ligand_platform_ready": False,
            "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
        },
        "rows": [
            {"domain": "transporter", "status": "blocked", "artifact": "runs/transporter.json", "observed": "p0_open=6"},
            {"domain": "ca2", "status": "ready", "artifact": "runs/ca2.json", "observed": "verified=7"},
            {"domain": "pxr", "status": "blocked", "artifact": "runs/pxr.json", "observed": "blocked_rows=6"},
            {"domain": "idp_broad", "status": "ready", "artifact": "runs/idp.json", "observed": "bounded=true"},
            {"domain": "all_atom", "status": "ready", "artifact": "runs/allatom.json", "observed": "claim_ready=true"},
        ],
    }


def _capability_packet() -> dict[str, object]:
    return {
        "summary": {
            "allowed_scope_families": ["gpcr", "ion_channel", "kinase"],
            "api_surface_ready": True,
            "general_protein_ligand_platform_ready": False,
        }
    }


def test_general_protein_ligand_claim_blocker_requires_domains_scope_count_and_flag() -> None:
    payload = mod.build_payload(scope_payload=_scope_packet(), capability_payload=_capability_packet())

    summary = payload["summary"]
    assert summary["general_protein_ligand_claim_allowed"] is False
    assert summary["ready_domains"] == ["ca2", "idp_broad", "all_atom"]
    assert summary["missing_domains"] == ["transporter", "pxr"]
    assert summary["allowed_scope_family_count"] == 3
    assert summary["explicit_general_platform_flag"] is False
    assert "domain_ready.transporter" in summary["blockers"]
    assert "domain_ready.pxr" in summary["blockers"]
    assert "allowed_scope_family_count" in summary["blockers"]
    assert "explicit_general_platform_flag" in summary["blockers"]


def test_general_protein_ligand_claim_blocker_allows_only_when_all_prereqs_green() -> None:
    scope = _scope_packet()
    scope["summary"] = {
        "scope_breadth_ready": True,
        "general_protein_ligand_platform_ready": True,
        "allowed_scope_families": ["gpcr", "ion_channel", "kinase", "transporter", "ca2", "pxr"],
    }
    for row in scope["rows"]:
        row["status"] = "ready"
    capability = {
        "summary": {
            "allowed_scope_families": ["gpcr", "ion_channel", "kinase", "transporter", "ca2", "pxr"],
            "api_surface_ready": True,
            "general_protein_ligand_platform_ready": True,
        }
    }

    payload = mod.build_payload(scope_payload=scope, capability_payload=capability)

    assert payload["summary"]["general_protein_ligand_claim_allowed"] is True
    assert payload["summary"]["blocker_count"] == 0


def test_general_protein_ligand_claim_blocker_cli_writes_outputs(tmp_path: Path) -> None:
    scope = tmp_path / "scope.json"
    capability = tmp_path / "capability.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    scope.write_text(json.dumps(_scope_packet()), encoding="utf-8")
    capability.write_text(json.dumps(_capability_packet()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_general_protein_ligand_claim_blocker_packet.py",
            "--scope-json",
            str(scope),
            "--capability-json",
            str(capability),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["general_protein_ligand_claim_allowed"] is False
    assert "General Protein-Ligand Claim Blocker Packet" in out_md.read_text(encoding="utf-8")
    assert "check_id" in out_csv.read_text(encoding="utf-8")
