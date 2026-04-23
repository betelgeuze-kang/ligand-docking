from __future__ import annotations

from tools import build_wetlab_priority3_target_render_split as mod


def test_build_wetlab_priority3_target_render_split() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_priority3_target_render_split_ready"
    assert summary["target_count"] == 3
    assert rows["T. cruzi PDE"]["planned_partner_export_artifact"] == "runs/tcruzi_pde_dndi_ipk_export_current.md"
    assert rows["CA IX"]["planned_selectivity_panel_artifact"] == "runs/caix_ca2_ca12_selectivity_panel_current.md"
    assert rows["SARS-CoV-2 Mpro"]["existing_compound_fill_artifacts"].endswith("runs/wetlab_mpro_vendor_cost_check_current.md")
