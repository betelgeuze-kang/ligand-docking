from __future__ import annotations

from tools import build_wetlab_domain_generation_schema as mod


def test_build_wetlab_domain_generation_schema() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = {row["domain_family"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_domain_generation_schema_ready"
    assert summary["domain_family_count"] == 5
    assert summary["renderer_layer_count"] == 3
    assert rows["carbonic_anhydrase"]["default_partner_tracks"] == "oncology_condition_aware"
    assert "buffer_pH" in rows["parasite_pde"]["condition_overlay_fields"]
    assert "host_cysteine_protease_panel" in rows["cysteine_protease"]["selectivity_overlay_fields"]
