from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_f2g_f2h_surface_preflight as mod


def test_f2g_f2h_surface_preflight_blocks_empty_checkout(tmp_path: Path) -> None:
    payload = mod.build_f2g_f2h_surface_preflight(root=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "blocked_f2g_f2h_surface_preflight"
    assert summary["blocker_count"] >= 6
    assert "real_mgt_input_surface_missing" in summary["blockers"]
    assert "f2h_blocked_until_f2g_audit" in summary["blockers"]
    assert summary["f2h_continuation_allowed"] is False
    assert summary["g1_promotion_allowed"] is False
    assert summary["protected_runs_artifact_written"] is False


def test_f2g_f2h_surface_preflight_detects_restored_surfaces(tmp_path: Path) -> None:
    productization = tmp_path / "implementation" / "phase1" / "release_evidence" / "productization"
    productization.mkdir(parents=True)
    for rel in [
        "implementation/phase1/real_mgt_model_packet.json",
        "implementation/phase1/real_per_element_assembled_tangent.json",
        "implementation/phase1/pr61_near_null_modes.json",
        "implementation/phase1/support_elastic_link_context.json",
        "implementation/phase1/lightweight_load_continuation_newton_driver.py",
        "implementation/phase1/release_evidence/productization/g1_support_elastic_link_reconciliation_audit.local.json",
    ]:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    payload = mod.build_f2g_f2h_surface_preflight(root=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "f2g_f2h_surface_preflight_ready"
    assert summary["blockers"] == []
    assert summary["real_mgt_candidate_count"] == 1
    assert summary["f2g_audit_ready"] is True
    assert summary["f2h_continuation_allowed"] is False
    assert summary["g1_promotion_allowed"] is False


def test_f2h_blocks_when_f2g_audit_is_missing_even_with_inputs(tmp_path: Path) -> None:
    (tmp_path / "implementation" / "phase1" / "release_evidence" / "productization").mkdir(parents=True)
    for rel in [
        "implementation/phase1/real_mgt_model_packet.json",
        "implementation/phase1/real_per_element_assembled_tangent.json",
        "implementation/phase1/pr61_near_null_modes.json",
        "implementation/phase1/support_elastic_link_context.json",
        "implementation/phase1/lightweight_load_continuation_newton_driver.py",
    ]:
        path = tmp_path / rel
        path.write_text("{}\n", encoding="utf-8")

    payload = mod.build_f2g_f2h_surface_preflight(root=tmp_path)

    assert "f2g_audit_not_available" in payload["summary"]["blockers"]
    assert "f2h_blocked_until_f2g_audit" in payload["summary"]["blockers"]


def test_cli_writes_local_json_csv_and_markdown(tmp_path: Path) -> None:
    out_json = tmp_path / "preflight.json"
    out_csv = tmp_path / "preflight.csv"
    out_md = tmp_path / "preflight.md"

    mod.main(["--root", str(tmp_path), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["packet_type"] == "f2g_f2h_surface_preflight"
    assert out_csv.read_text(encoding="utf-8").startswith("check_id,status,")
    assert "F2g/F2h Surface Preflight" in out_md.read_text(encoding="utf-8")
